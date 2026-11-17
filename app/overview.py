"""Live inventory totals for the overview page."""
import psycopg
from psycopg import sql


def read_overview(database_url, schema):
    with psycopg.connect(database_url, connect_timeout=8) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '5000ms'")
        query = sql.SQL("""
            SELECT count(*), count(DISTINCT e.source_id), min(e.period_year), max(e.period_year),
                   count(*) FILTER (WHERE e.validation_status = 'VERIFIED')
            FROM {}.lci_exchange e
        """).format(sql.Identifier(schema))
        total, sources, first, last, verified = conn.execute(query).fetchone()
    return dict(exchanges=total, sources=sources, first_year=first, last_year=last, verified=verified)
