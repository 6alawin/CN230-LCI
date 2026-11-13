from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import psycopg

from app.config import get_settings
from app.search import embed_query


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)
    source_code: str | None = Field(default=None, pattern=r"^SRC-\d{2}$")


app = FastAPI(title="CN230 LCI Semantic Search", version="0.1.0")


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/api/health")
def health():
    try:
        settings = get_settings()
        with psycopg.connect(settings.database_url, connect_timeout=8) as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable or DATABASE_URL is not configured") from exc


@app.post("/api/search")
def search(request: SearchRequest):
    try:
        settings = get_settings()
        vector = embed_query(request.query, settings)
        vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
        with psycopg.connect(settings.database_url, connect_timeout=8) as conn:
            rows = conn.execute(
                """
                SELECT entity_type, entity_id, title, content, source_code,
                       metadata, 1 - (embedding <=> %s::vector) AS similarity
                FROM semantic_search_documents
                WHERE (%s IS NULL OR source_code = %s)
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
        raise HTTPException(status_code=503, detail="Search is not ready; check DATABASE_URL, pgvector setup, and Gemini configuration") from exc
