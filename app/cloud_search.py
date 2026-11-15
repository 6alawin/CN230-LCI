"""CPU embedding inference and retrieval from a versioned Render snapshot."""
from functools import lru_cache
from pathlib import Path
import re
import psycopg
from psycopg import sql

def requested_years(query):
    """Extract explicitly written Gregorian/Buddhist years without guessing dates."""
    normalized = query.translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789'))
    matches = list(re.finditer(r'(?<![\d.])(?:19\d{2}|20\d{2}|25\d{2})(?![\d.])', normalized))
    years = []
    for match in matches:
        year = int(match.group())
        # A Buddhist year is ambiguous without an adjacent year marker.
        if year >= 2500:
            before = normalized[max(0, match.start()-12):match.start()]
            continuing_range = (years and 2500 <= int(matches[0].group()) <= 2599 and
                                re.fullmatch(r'\s*(?:-|–|—|ถึง|to)\s*', normalized[years[-1][2]:match.start()], re.IGNORECASE))
            if not re.search(r'(?:พ\.?ศ\.?|ปี)\s*$', before) and not continuing_range:
                continue
            year -= 543
        years.append((year, match.start(), match.end()))
    if len(years) == 2:
        between = normalized[years[0][2]:years[1][1]]
        if re.fullmatch(r'\s*(?:-|–|—|ถึง|to)\s*(?:พ\.?ศ\.?\s*)?', between, re.IGNORECASE):
            low, high = sorted((years[0][0], years[1][0]))
            if high - low <= 100:
                return list(range(low, high + 1))
    return sorted({year for year, _, _ in years})

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
    years = requested_years(request.query)
    # When searching all sources, retain the best item from each source. Many
    # near-identical monthly rows otherwise crowd every other source out.
    query=sql.SQL('''WITH ranked AS MATERIALIZED (
        SELECT d.exchange_id,d.title,d.content,d.source_code,d.embedding,
            row_number() OVER (PARTITION BY d.source_code ORDER BY d.embedding <=> %s::public.vector) AS rn
        FROM {}.semantic_local_documents d JOIN {}.lci_exchange e ON e.exchange_id=d.exchange_id
        WHERE (%s::integer[] IS NULL OR e.period_year = ANY(%s::integer[])))
        SELECT exchange_id,title,content,source_code,
            1-(embedding <=> %s::public.vector) AS similarity
        FROM ranked WHERE rn=1 ORDER BY similarity DESC LIMIT %s''').format(sql.Identifier(settings.cloud_snapshot_schema),sql.Identifier(settings.cloud_snapshot_schema))
    with psycopg.connect(settings.database_url,connect_timeout=15) as conn:
        if request.source_code:
            # Rank all rows in the requested source; a global approximate index
            # can otherwise discard source matches before applying LIMIT.
            filtered=sql.SQL('''WITH candidates AS MATERIALIZED (
                SELECT d.* FROM {}.semantic_local_documents d
                JOIN {}.lci_exchange e ON e.exchange_id=d.exchange_id
                WHERE d.source_code=%s AND (%s::integer[] IS NULL OR e.period_year = ANY(%s::integer[])))
                SELECT exchange_id,title,content,source_code,
                    1-(embedding <=> %s::public.vector) AS similarity
                FROM candidates ORDER BY embedding <=> %s::public.vector LIMIT %s''').format(sql.Identifier(settings.cloud_snapshot_schema),sql.Identifier(settings.cloud_snapshot_schema))
            rows=conn.execute(filtered,(request.source_code,years or None,years or None,literal,literal,request.limit)).fetchall()
        else:
            rows=conn.execute(query,(literal,years or None,years or None,literal,request.limit)).fetchall()
    return {'query':request.query,'backend':'local_model_on_cloud','embedding_model':settings.local_embedding_model,
        'year_filter': years,
        'results':[{'entity_type':'exchange','entity_id':r[0],'title':r[1],'content':r[2],'source_code':r[3],
                    'similarity':float(r[4]),'metadata':{}} for r in rows]}
