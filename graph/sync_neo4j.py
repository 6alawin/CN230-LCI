"""Copy the PostgreSQL LCI model into Neo4j as a graph."""

from __future__ import annotations

import argparse
import os
import sys

import psycopg
from neo4j import GraphDatabase
from psycopg.rows import dict_row


QUERY = """
SELECT
    p.process_id, p.name AS process_name, p.process_type,
    loc.location_id, loc.country,
    pf.direction,
    f.flow_id, f.name AS flow_name, f.product_type,
    e.exchange_id, e.amount::float8 AS amount, e.amount::text AS amount_exact,
    e.period_year, e.period_month,
    e.validation_status, e.note,
    u.unit_id, u.symbol AS unit_symbol, u.quantity_type,
    u.to_base_factor::float8 AS to_base_factor,
    s.source_id, s.src_code, s.dataset_name, s.agency, s.data_owner, s.url
FROM lci_exchange e
JOIN process_flow pf ON pf.process_flow_id = e.process_flow_id
JOIN process p ON p.process_id = pf.process_id
JOIN location loc ON loc.location_id = p.location_id
JOIN flow f ON f.flow_id = pf.flow_id
JOIN unit u ON u.unit_id = e.unit_id
JOIN source s ON s.source_id = e.source_id
ORDER BY e.exchange_id
"""

UNIT_CATALOG_QUERY = """
SELECT unit_id, symbol AS unit_symbol, quantity_type,
       to_base_factor::float8 AS to_base_factor
FROM unit
ORDER BY unit_id
"""

UPSERT_UNITS = """
UNWIND $rows AS row
MERGE (u:Unit {id: row.unit_id})
SET u.symbol = row.unit_symbol, u.quantity_type = row.quantity_type,
    u.to_base_factor = row.to_base_factor
"""


UPSERT_BATCH = """
UNWIND $rows AS row
MERGE (p:Process {id: row.process_id})
SET p.name = row.process_name, p.process_type = row.process_type
MERGE (loc:Location {id: row.location_id})
SET loc.country = row.country
MERGE (p)-[:LOCATED_IN]->(loc)
MERGE (f:Flow {id: row.flow_id})
SET f.name = row.flow_name, f.product_type = row.product_type
MERGE (s:Source {id: row.source_id})
SET s.code = row.src_code, s.dataset_name = row.dataset_name,
    s.agency = row.agency, s.data_owner = row.data_owner, s.url = row.url
MERGE (u:Unit {id: row.unit_id})
SET u.symbol = row.unit_symbol, u.quantity_type = row.quantity_type,
    u.to_base_factor = row.to_base_factor
MERGE (e:Exchange {id: row.exchange_id})
SET e.amount = row.amount, e.amount_exact = row.amount_exact,
    e.period_year = row.period_year,
    e.period_month = row.period_month, e.validation_status = row.validation_status,
    e.note = row.note
MERGE (p)-[:HAS_EXCHANGE]->(e)
MERGE (e)-[uses:USES_FLOW]->(f)
SET uses.direction = row.direction
MERGE (e)-[:REPORTED_BY]->(s)
MERGE (e)-[:MEASURED_IN]->(u)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="delete all existing Neo4j nodes and relationships before syncing")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")

    pg_conninfo = " ".join(
        (
            f"host={os.getenv('PGHOST', 'db')}",
            f"port={os.getenv('PGPORT', '5432')}",
            f"dbname={os.getenv('PGDATABASE', 'cn230lci')}",
            f"user={os.getenv('PGUSER', 'cn230lci')}",
            f"password={os.getenv('PGPASSWORD', 'portugalsql')}",
        )
    )
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "cn230lci2026")

    try:
        with GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password)) as driver:
            driver.verify_connectivity()
            with driver.session() as session:
                session.run("CREATE CONSTRAINT process_id IF NOT EXISTS FOR (n:Process) REQUIRE n.id IS UNIQUE").consume()
                session.run("CREATE CONSTRAINT flow_id IF NOT EXISTS FOR (n:Flow) REQUIRE n.id IS UNIQUE").consume()
                session.run("CREATE CONSTRAINT location_id IF NOT EXISTS FOR (n:Location) REQUIRE n.id IS UNIQUE").consume()
                session.run("CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.id IS UNIQUE").consume()
                session.run("CREATE CONSTRAINT unit_id IF NOT EXISTS FOR (n:Unit) REQUIRE n.id IS UNIQUE").consume()
                session.run("CREATE CONSTRAINT exchange_id IF NOT EXISTS FOR (n:Exchange) REQUIRE n.id IS UNIQUE").consume()
                if args.reset:
                    session.run("MATCH (n) DETACH DELETE n").consume()
                    # Recreate constraints after clearing the graph.
                    session.run("CREATE CONSTRAINT process_id IF NOT EXISTS FOR (n:Process) REQUIRE n.id IS UNIQUE").consume()
                    session.run("CREATE CONSTRAINT flow_id IF NOT EXISTS FOR (n:Flow) REQUIRE n.id IS UNIQUE").consume()
                    session.run("CREATE CONSTRAINT location_id IF NOT EXISTS FOR (n:Location) REQUIRE n.id IS UNIQUE").consume()
                    session.run("CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.id IS UNIQUE").consume()
                    session.run("CREATE CONSTRAINT unit_id IF NOT EXISTS FOR (n:Unit) REQUIRE n.id IS UNIQUE").consume()
                    session.run("CREATE CONSTRAINT exchange_id IF NOT EXISTS FOR (n:Exchange) REQUIRE n.id IS UNIQUE").consume()

                total = 0
                with psycopg.connect(pg_conninfo, row_factory=dict_row) as pg:
                    unit_rows = pg.execute(UNIT_CATALOG_QUERY).fetchall()
                    if unit_rows:
                        session.run(UPSERT_UNITS, rows=unit_rows).consume()
                    with pg.cursor(name="lci_exchange_cursor") as cursor:
                        cursor.execute(QUERY)
                        while rows := cursor.fetchmany(args.batch_size):
                            session.run(UPSERT_BATCH, rows=rows).consume()
                            total += len(rows)
                            print(f"Synced {total:,} exchanges", flush=True)
            print(f"Done. Synced {total:,} exchanges to {neo4j_uri}")
        return 0
    except Exception as exc:  # print a useful message in a simple beginner workflow
        print(f"Neo4j sync failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
