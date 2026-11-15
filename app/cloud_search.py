"""CPU embedding inference and retrieval from a versioned Render snapshot."""
from functools import lru_cache
from pathlib import Path
import psycopg
from psycopg import sql

@lru_cache(maxsize=1)
def load_model(model_id, model_path):
    from app.cpu_embedding import CpuEmbedding
    path=Path(model_path)
    if not path.is_dir():
        raise RuntimeError('Cloud embedding model is missing; run the cloud build command')
    return CpuEmbedding(path)

def search_cloud(request, settings):
    model=load_model(settings.local_embedding_model,settings.local_model_path)
    v=model.encode([request.query],normalize_embeddings=True,convert_to_numpy=True)[0]
    if len(v)!=384:raise RuntimeError('Expected 384-dimensional embeddings')
    literal='['+','.join(str(float(x)) for x in v)+']'
    query=sql.SQL('''SELECT exchange_id,title,content,source_code,
           1-(embedding <=> %s::public.vector) AS similarity
        FROM {}.semantic_local_documents
        WHERE (%s::text IS NULL OR source_code=%s::text)
        ORDER BY embedding <=> %s::public.vector LIMIT %s''').format(sql.Identifier(settings.cloud_snapshot_schema))
    with psycopg.connect(settings.database_url,connect_timeout=15) as conn:
        if request.source_code:
            # Rank all rows in the requested source; a global approximate index
            # can otherwise discard source matches before applying LIMIT.
            filtered=sql.SQL('''WITH candidates AS MATERIALIZED (
                SELECT * FROM {}.semantic_local_documents WHERE source_code=%s)
                SELECT exchange_id,title,content,source_code,
                    1-(embedding <=> %s::public.vector) AS similarity
                FROM candidates ORDER BY embedding <=> %s::public.vector LIMIT %s''').format(sql.Identifier(settings.cloud_snapshot_schema))
            rows=conn.execute(filtered,(request.source_code,literal,literal,request.limit)).fetchall()
        else:
            rows=conn.execute(query,(literal,None,None,literal,request.limit)).fetchall()
    return {'query':request.query,'backend':'local_model_on_cloud','embedding_model':settings.local_embedding_model,
        'results':[{'entity_type':'exchange','entity_id':r[0],'title':r[1],'content':r[2],'source_code':r[3],
                    'similarity':float(r[4]),'metadata':{}} for r in rows]}
