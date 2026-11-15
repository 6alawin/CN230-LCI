"""Upload a new verified schema; never modify existing Render tables."""
from pathlib import Path
import json
import os
import numpy as np
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from inspect_render_sync import remote_url

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='lci_verified_20261115'
tables=['source','location','unit','process','flow','process_flow','lci_exchange','lci_import_log']
with psycopg.connect(os.environ['LOCAL_DATABASE_URL'],row_factory=dict_row) as local:
    local.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    data={t:local.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(t))).fetchall() for t in tables}
if any(r['validation_status']!='VERIFIED' for r in data['lci_exchange']):raise RuntimeError('Unverified Local rows')
with np.load(ROOT/'local_lci_index.npz',allow_pickle=False) as f:
    docs=[json.loads(x) for x in f['documents']];vectors=f['vectors']
if {d['entity_id'] for d in docs}!={r['exchange_id'] for r in data['lci_exchange']}:raise RuntimeError('Index IDs mismatch')
with psycopg.connect(remote_url(),connect_timeout=20) as remote:
    if remote.execute('SELECT 1 FROM information_schema.schemata WHERE schema_name=%s',(SCHEMA,)).fetchone():raise RuntimeError('Snapshot schema already exists; no overwrite attempted')
    remote.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(SCHEMA)))
    remote.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(SCHEMA)))
    remote.execute((ROOT.parent/'initdb'/'001_schema.sql').read_text(encoding='utf-8'))
    for t in tables:
        rows=data[t]
        if rows:
            cols=list(rows[0])
            with remote.cursor() as cur:
                with cur.copy(sql.SQL('COPY {} ({}) FROM STDIN').format(sql.Identifier(t),sql.SQL(',').join(map(sql.Identifier,cols)))) as cp:
                    for row in rows:cp.write_row(tuple(Jsonb(row[c]) if isinstance(row[c],dict) else row[c] for c in cols))
            key={'source':'source_id','location':'location_id','unit':'unit_id','process':'process_id','flow':'flow_id','process_flow':'process_flow_id','lci_exchange':'exchange_id','lci_import_log':'import_log_id'}[t]
            seq=remote.execute('SELECT pg_get_serial_sequence(%s,%s)',(SCHEMA+'.'+t,key)).fetchone()[0]
            remote.execute(sql.SQL('SELECT setval(%s,(SELECT max({}) FROM {}),true)').format(sql.Identifier(key),sql.Identifier(t)),(seq,))
        print(t,len(rows),flush=True)
    remote.execute('CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public')
    remote.execute('''CREATE TABLE semantic_local_documents(exchange_id integer PRIMARY KEY REFERENCES lci_exchange(exchange_id),
    source_code text NOT NULL,title text NOT NULL,content text NOT NULL,embedding public.vector(384) NOT NULL,
    model text NOT NULL,indexed_at timestamptz NOT NULL DEFAULT now())''')
    with remote.cursor() as cur:
        with cur.copy('COPY semantic_local_documents(exchange_id,source_code,title,content,embedding,model) FROM STDIN') as cp:
            for doc,v in zip(docs,vectors):
                cp.write_row((doc['entity_id'],doc['source_code'],doc['title'],doc['content'],'['+','.join(str(float(x)) for x in v)+']','sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'))
    remote.execute('CREATE INDEX semantic_local_embedding_idx ON semantic_local_documents USING hnsw(embedding public.vector_cosine_ops)')
    remote.execute('CREATE INDEX semantic_local_source_idx ON semantic_local_documents(source_code)')
    count=remote.execute('SELECT count(*) FROM semantic_local_documents').fetchone()[0]
    if count!=40721:raise RuntimeError('Unexpected snapshot count')
    print('Snapshot ready to commit:',SCHEMA,count,flush=True)
print('New Render snapshot committed; existing schemas untouched',flush=True)
