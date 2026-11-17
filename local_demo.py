"""Local-only LCI semantic search and Ollama RAG."""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from app.query_workbench import run_sql
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'local_lci_index.npz'
DATABASE_URL = os.environ.get('LCI_LOCAL_DATABASE_URL', 'postgresql://cn230lci:portugalsql@localhost:5433/cn230lci')
MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
OLLAMA = 'http://127.0.0.1:11434/api/generate'
_model = None
_index = None
_index_mtime = None

def model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL)
    return _model

def build_index():
    global _index
    sql = '''SELECT e.exchange_id, s.src_code, s.dataset_name, p.name, p.process_type,
                    f.name, f.product_type, pf.direction, e.amount::text, u.symbol,
                    e.period_year, e.period_month, e.validation_status
             FROM lci_exchange e JOIN source s ON s.source_id=e.source_id
             JOIN process_flow pf ON pf.process_flow_id=e.process_flow_id
             JOIN process p ON p.process_id=pf.process_id JOIN flow f ON f.flow_id=pf.flow_id
             JOIN unit u ON u.unit_id=e.unit_id ORDER BY e.exchange_id'''
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute(sql).fetchall()
    docs = []
    for eid, src, dataset, process, ptype, flow, product, direction, amount, unit, year, month, status in rows:
        period = f'{year}-{month:02d}' if month else str(year)
        text = f'แหล่งข้อมูล {src} {dataset} กระบวนการ {process} ประเภท {ptype} ผลิตภัณฑ์ {flow} ประเภท {product} ทิศทาง {direction} ปริมาณ {amount} {unit} ช่วงเวลา {period} สถานะ {status}'
        docs.append({'entity_id': eid, 'source_code': src, 'title': f'{src}: {flow} / {process} / {period}', 'content': text})
    if not docs:
        raise RuntimeError('ไม่พบข้อมูล Exchange ในฐานข้อมูล')
    vectors = model().encode([d['content'] for d in docs], batch_size=32, normalize_embeddings=True, show_progress_bar=True, convert_to_numpy=True)
    np.savez_compressed(INDEX, vectors=vectors.astype(np.float32), documents=np.array([json.dumps(d, ensure_ascii=False) for d in docs]))
    _index = None
    return len(docs)

def load_index():
    global _index, _index_mtime
    mtime = INDEX.stat().st_mtime_ns
    if _index is None or _index_mtime != mtime:
        with np.load(INDEX, allow_pickle=False) as data:
            _index = (data['vectors'], [json.loads(x) for x in data['documents']])
        _index_mtime = mtime
    return _index

def search(query, source_code=None, limit=10):
    vectors, docs = load_index()
    q = model().encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
    scores = vectors @ q
    candidates = [i for i in np.argsort(-scores) if not source_code or docs[i]['source_code'] == source_code][:limit]
    return [dict(docs[i], similarity=float(scores[i])) for i in candidates]

def answer(query, hits):
    if not hits:
        return 'ไม่พบข้อมูลที่เกี่ยวข้อง'
    evidence = '\n'.join(f"[{h['source_code']} / exchange {h['entity_id']}] {h['content']}" for h in hits[:8])
    prompt = f'ตอบคำถามเป็นภาษาไทยโดยอิงเฉพาะหลักฐานด้านล่าง อ้างรหัส SRC และ exchange ที่ใช้จริง ห้ามอ้างแหล่งที่ไม่มีในหลักฐาน ห้ามสรุปข้ามภาคเศรษฐกิจ ช่วงเวลา หรือหน่วย หากหลักฐานไม่เพียงพอให้บอกชัดเจนว่าข้อมูลไม่เพียงพอ ห้ามสมมติหรือคำนวณเพิ่ม ใช้ข้อความธรรมดาโดยไม่ใช้ LaTeX\nคำถาม: {query}\nหลักฐาน:\n{evidence}'
    request = Request(OLLAMA, data=json.dumps({'model':'gemma4:e2b','prompt':prompt,'stream':False}, ensure_ascii=False).encode('utf-8'), headers={'Content-Type':'application/json'})
    with urlopen(request, timeout=300) as response:
        return json.load(response)['response']

class SearchRequest(BaseModel):
    query: str
    source_code: str | None = None
    limit: int = 10

class QueryRequest(BaseModel):
    language: str
    query: str

app = FastAPI()
app.mount("/assets", StaticFiles(directory=ROOT / "static"), name="assets")

@app.get('/')
def home():
    return FileResponse(ROOT / 'static' / 'index.html')

@app.get('/query')
def query_page():
    return FileResponse(ROOT / 'static' / 'query.html')

@app.post('/api/query')
def api_query(request: QueryRequest):
    if len(request.query) > 5000:
        raise HTTPException(status_code=400, detail='คำสั่งยาวเกิน 5,000 ตัวอักษร')
    try:
        if request.language == 'sql':
            return run_sql(DATABASE_URL, request.query)
        if request.language == 'cypher':
            statement = request.query.strip().rstrip(';').strip()
            if not statement.upper().startswith(('MATCH ', 'OPTIONAL MATCH ', 'WITH ')) or ';' in statement:
                raise ValueError('รองรับ Cypher แบบอ่านข้อมูลครั้งละหนึ่งคำสั่ง')
            uri = os.environ.get('NEO4J_URI', 'bolt://127.0.0.1:7687')
            password = os.environ.get('NEO4J_PASSWORD', 'cn230lci2026')
            with GraphDatabase.driver(uri, auth=('neo4j', password)) as driver:
                with driver.session() as session:
                    records = session.execute_read(lambda tx: list(tx.run(statement).fetch(101)))
            return {'columns': list(records[0].keys()) if records else [],
                    'rows': [[str(value) if value is not None else None for value in record.values()]
                             for record in records[:100]], 'truncated': len(records) > 100}
        raise ValueError('เลือก SQL หรือ Cypher')
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/search')
def search_page():
    return FileResponse(ROOT / 'static' / 'search.html')

@app.get("/api/annual-flow")
def annual_flow(fuel: str = "all", year: int | None = None):
    from app.annual_flow import read_annual_flow

    try:
        return read_annual_flow(DATABASE_URL, 'public', fuel, year)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="อ่านข้อมูลรายปีไม่ได้") from exc


@app.get('/api/flow')
def flow(fuel: str = 'coal', year: int | None = None, month: int | None = None):
    from app.flow import read_flow
    try:
        if month is not None and not 1 <= month <= 12:
            raise ValueError('เดือนต้องอยู่ระหว่าง 1 ถึง 12')
        return read_flow(DATABASE_URL, 'public', fuel, year, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail='อ่านข้อมูลการไหลไม่ได้') from exc

@app.get('/api/overview')
def overview():
    from app.overview import read_overview
    try:
        return read_overview(DATABASE_URL, 'public')
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail='อ่านภาพรวมฐานข้อมูลไม่ได้') from exc

@app.get('/api/health')
def health():
    return {'status': 'ok' if INDEX.exists() else 'index_missing'}

@app.post('/api/search')
def api_search(request: SearchRequest):
    try:
        hits = search(request.query, request.source_code, min(max(request.limit, 1), 50))
        try:
            result = answer(request.query, hits)
        except Exception:
            result = 'ไม่สามารถเชื่อม Ollama ได้ โปรดเปิด Ollama และตรวจว่า gemma4:e2b พร้อมใช้งาน'
        return {'query':request.query, 'results':hits, 'answer':result}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f'ค้นหาไม่ได้: {exc}') from exc
