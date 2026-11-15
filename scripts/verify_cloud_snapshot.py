"""Verify the uploaded snapshot and exercise cloud retrieval without secrets in output."""
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from inspect_render_sync import remote_url
from app.cloud_search import search_cloud

settings=SimpleNamespace(database_url=remote_url(),
    local_embedding_model='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
    local_model_path='models/lci-embedding',cloud_snapshot_schema='lci_verified_20261115')
with psycopg.connect(settings.database_url,connect_timeout=20) as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    count=conn.execute('SELECT count(*),count(DISTINCT exchange_id) FROM lci_verified_20261115.lci_exchange').fetchone()
    vectors=conn.execute('SELECT count(*),min(vector_dims(embedding)),max(vector_dims(embedding)) FROM lci_verified_20261115.semantic_local_documents').fetchone()
    sources=conn.execute('SELECT count(*) FROM lci_verified_20261115.source').fetchone()[0]
    assert count==(40721,40721),count
    assert vectors==(40721,384,384),vectors
    assert sources==21,sources
    print('Verified snapshot: 40,721 unique Exchange; 21 Sources; 40,721 vectors (384-D)')
for source in [None,'SRC-21']:
    result=search_cloud(SimpleNamespace(query='การปล่อยคาร์บอนจากการผลิตไฟฟ้า',limit=3,source_code=source),settings)
    assert len(result['results'])==3
    if source:assert all(r['source_code']==source for r in result['results'])
    print('Search OK:',source or 'all sources',[(r['entity_id'],r['source_code'],round(r['similarity'],3)) for r in result['results']])
