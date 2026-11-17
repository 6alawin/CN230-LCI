"""Read chronological LCI observations, validation issues and unit definitions."""
from calendar import month_name
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query
import psycopg
from psycopg import sql
from psycopg.rows import dict_row


EXCHANGES = """
    SELECT e.exchange_id AS id, f.name AS flow, p.name AS process,
           p.process_type, pf.direction, f.product_type, e.amount::text AS amount,
           u.symbol AS unit, e.period_year AS year, e.period_month AS month,
           s.src_code AS source, e.validation_status AS status, e.note
    FROM lci_exchange e
    JOIN process_flow pf USING (process_flow_id)
    JOIN process p USING (process_id)
    JOIN flow f USING (flow_id)
    JOIN unit u USING (unit_id)
    JOIN source s USING (source_id)
    WHERE e.period_year = %s
    ORDER BY e.period_month NULLS LAST, s.src_code, e.exchange_id
"""

ISSUES = """
    SELECT s.src_code AS source, l.source_line AS line, l.status, l.reason,
           l.raw_data AS raw
    FROM lci_import_log l JOIN source s USING (source_id)
    WHERE l.resolved_at IS NULL AND trim(l.raw_data->>'Year') = %s
    ORDER BY s.src_code, l.source_line
"""

FUEL_TYPES = {"OIL": "oil", "NATURAL_GAS": "gas", "COAL": "coal", "BIOFUEL": "bio"}
EMISSION_FUELS = {"CO2 - OIL": "oil", "CO2 - NATURAL GAS": "gas", "CO2 - COAL / LIGNITE": "coal"}
MONTHS = {name.lower(): index for index, name in enumerate(month_name) if name}


def classify_exchange(row):
    """Derive display categories from the recorded source, process and flow."""
    process_type = row["process_type"]
    source = row["source"]
    flow = row["flow"].upper()
    if process_type == "EMISSION":
        fuel = EMISSION_FUELS.get(flow, "other")
    elif flow == "LPG":
        fuel = "lpg"
    else:
        fuel = FUEL_TYPES.get(row["product_type"], "other")

    # SRC-12 เก็บการกระจาย NGL ส่วน SRC-11 มีปริมาณก๊าซเข้าโรงแยกก๊าซ (GSP)
    if source == "SRC-12" and process_type == "DISTRIBUTION" or (
        source == "SRC-11" and row["process"].upper() == "GSP"
    ):
        stage = 1
    elif process_type == "REFINING" or (
        process_type == "PRODUCTION" and source in {"SRC-05", "SRC-09", "SRC-16", "SRC-17"}
    ):
        stage = 2
    elif process_type in {"EXPORT", "DISTRIBUTION"}:
        stage = 3
    elif process_type in {"DOMESTIC_USE", "EMISSION"}:
        stage = 4
    else:
        stage = 0

    # role ใช้คัดรายการที่เข้าเงื่อนไขเท่านั้น การรวมยังต้องตรวจหน่วย ช่วงเวลาและขอบเขต
    role = None
    if process_type in {"PRODUCTION", "IMPORT"}:
        role = "supply"
    elif process_type == "DOMESTIC_USE":
        role = "demand"
    elif process_type == "EMISSION":
        role = "emission"
    row.update(fuel=fuel, stage=stage, role=role)
    return row


def make_energy_router(get_target):
    router = APIRouter(prefix="/api/energy")

    @contextmanager
    def connection():
        url, schema = get_target()
        try:
            with psycopg.connect(url, connect_timeout=8, row_factory=dict_row) as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                conn.execute("SET LOCAL statement_timeout = '8000ms'")
                conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
                yield conn
        except psycopg.Error as exc:
            raise HTTPException(503, "อ่านฐานข้อมูล LCI ไม่สำเร็จ") from exc

    @router.get("/periods")
    def periods():
        with connection() as conn:
            rows = conn.execute("""
                SELECT DISTINCT period_year AS year, period_month AS month
                FROM lci_exchange ORDER BY year, month NULLS LAST
            """).fetchall()
        return {"periods": rows}

    @router.get("/units")
    def units():
        with connection() as conn:
            rows = conn.execute("""
                SELECT symbol, quantity_type, to_base_factor::text AS to_base_factor
                FROM unit ORDER BY quantity_type, symbol
            """).fetchall()
        return {"units": rows}

    @router.get("/rows")
    def year_rows(year: int = Query(ge=1, le=9999)):
        with connection() as conn:
            rows = [classify_exchange(row) for row in conn.execute(EXCHANGES, (year,))]
            has_log = conn.execute("SELECT to_regclass('lci_import_log') IS NOT NULL AS present").fetchone()["present"]
            issues = conn.execute(ISSUES, (str(year),)).fetchall() if has_log else []
            for issue in issues:
                issue["year"] = year
                issue["month"] = MONTHS.get(str(issue["raw"].get("Month", "")).strip().lower())
        return {"rows": rows, "issues": issues, "log_available": has_log}

    return router
