from fastapi import FastAPI, HTTPException
from app.energy_data import make_energy_router
from app.source_files import router as source_files_router
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import psycopg

from app.config import get_settings


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)
    source_code: str | None = Field(default=None, pattern=r"^SRC-\d{2}$")


class QueryRequest(BaseModel):
    language: str
    query: str = Field(min_length=1, max_length=5000)


app = FastAPI(title="CN230 LCI Semantic Search", version="0.1.0")
app.include_router(source_files_router)
app.include_router(make_energy_router(lambda: (get_settings().database_url, get_settings().cloud_snapshot_schema)))
app.mount("/assets", StaticFiles(directory="static"), name="assets")


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/query")
def query_page():
    return FileResponse("static/query.html")


@app.post("/api/query")
def run_query(request: QueryRequest):
    from app.query_workbench import run_sql
    try:
        settings = get_settings()
        if request.language == "cypher":
            from app.cypher_workbench import run_cypher
            return run_cypher(request.query)
        if request.language != "sql":
            raise ValueError("เลือก SQL หรือ Cypher")
        return run_sql(settings.database_url, request.query, settings.cloud_snapshot_schema)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=400, detail="คำสั่ง SQL ไม่สำเร็จ กรุณาตรวจชื่อตารางและคอลัมน์") from exc



@app.get("/search")
def search_page():
    return FileResponse("static/search.html")

@app.get("/api/annual-flow")
def annual_flow(fuel: str = "all", year: int | None = None):
    from app.annual_flow import read_annual_flow
    settings = get_settings()
    try:
        return read_annual_flow(settings.database_url, settings.cloud_snapshot_schema, fuel, year)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="อ่านข้อมูลรายปีไม่ได้") from exc


@app.get("/api/flow")
def flow(fuel: str = "coal", year: int | None = None, month: int | None = None):
    from app.flow import read_flow
    settings = get_settings()
    try:
        if month is not None and not 1 <= month <= 12:
            raise ValueError("เดือนต้องอยู่ระหว่าง 1 ถึง 12")
        return read_flow(settings.database_url, settings.cloud_snapshot_schema, fuel, year, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="อ่านข้อมูลการไหลไม่ได้") from exc


@app.get("/api/overview")
def overview():
    from app.overview import read_overview
    settings = get_settings()
    try:
        return read_overview(settings.database_url, settings.cloud_snapshot_schema)
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="อ่านภาพรวมฐานข้อมูลไม่ได้") from exc

@app.get("/api/health")
def health():
    try:
        settings = get_settings()
        with psycopg.connect(settings.database_url, connect_timeout=8) as conn:
            conn.execute("SELECT 1")
            if settings.search_backend == 'local_model':
                from pathlib import Path
                if not all((Path(settings.local_model_path) / name).is_file() for name in
                           ('onnx/model_quint8_avx2.onnx', 'sentencepiece.bpe.model')):
                    raise RuntimeError('Embedding model has not been built')
                snapshot = settings.cloud_snapshot_schema + '.semantic_local_documents'
                if conn.execute('SELECT to_regclass(%s)', (snapshot,)).fetchone()[0] is None:
                    raise RuntimeError('Verified cloud snapshot is missing')
        return {"status": "ok", "database": "connected", "search_backend": settings.search_backend,
                "rag_configured": bool(settings.gemini_api_key)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable or DATABASE_URL is not configured") from exc


@app.post("/api/search")
def search(request: SearchRequest):
    try:
        settings = get_settings()
        if settings.search_backend == 'local_model':
            from app.cloud_search import requested_years, search_cloud
            from app.monthly import emission_report, emission_scope, monthly_report, monthly_scope
            years = requested_years(request.query)
            emission = emission_scope(request.query, years)
            if emission:
                return emission_report(request, settings, years[0], emission)
            scope = monthly_scope(request.query, years)
            if scope:
                return monthly_report(request, settings, years[0], scope)
            result = search_cloud(request, settings)
            from app.rag import generate_answer
            result['answer'], result['rag_message'] = generate_answer(request.query, result['results'], settings)
            return result
        from app.search import embed_query
        vector = embed_query(request.query, settings)
        vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
        with psycopg.connect(settings.database_url, connect_timeout=8) as conn:
            rows = conn.execute(
                """
                SELECT entity_type, entity_id, title, content, source_code,
                       metadata, 1 - (embedding <=> %s::vector) AS similarity
                FROM semantic_search_documents
                WHERE (%s::varchar IS NULL OR source_code = %s::varchar)
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vector_literal, request.source_code, request.source_code, vector_literal, request.limit),
            ).fetchall()
        return {
            "query": request.query,
            "results": [
                {
                    "entity_type": row[0], "entity_id": row[1], "title": row[2],
                    "content": row[3], "source_code": row[4], "metadata": row[5],
                    "similarity": float(row[6]),
                }
                for row in rows
            ],
        }
    except Exception as exc:
        # Do not expose DB credentials, SQL details, or provider errors to API clients.
        raise HTTPException(status_code=503, detail="Search is not ready; check database, embedding model, and search index configuration") from exc
