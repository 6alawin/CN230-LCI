"""Monthly fuel uses, reported products and emissions with separate provenance."""
import psycopg
from psycopg import sql

FUEL_TYPES = {"coal": "COAL", "gas": "NATURAL_GAS", "oil": "OIL"}
EMISSIONS = {"coal": "CO2 - COAL / LIGNITE", "gas": "CO2 - NATURAL GAS", "oil": "CO2 - OIL"}
USE_SOURCES = {"coal": ["SRC-15"], "gas": ["SRC-11"], "oil": ["SRC-08", "SRC-22"]}


def read_flow(database_url, schema, fuel, year=None, month=None):
    if fuel not in FUEL_TYPES:
        raise ValueError("เลือกถ่านหิน ก๊าซธรรมชาติ หรือน้ำมัน")
    if (year is None) != (month is None):
        raise ValueError("ระบุปีและเดือนพร้อมกัน")
    with psycopg.connect(database_url, connect_timeout=8) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '5000ms'")
        conn.execute(sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema)))
        periods = conn.execute("""SELECT DISTINCT e.period_year, e.period_month
            FROM lci_exchange e JOIN source s USING(source_id)
            WHERE s.src_code = ANY(%s) AND e.validation_status = 'VERIFIED'
            AND e.period_month BETWEEN 1 AND 12 ORDER BY 1 DESC, 2 DESC""", (USE_SOURCES[fuel],)).fetchall()
        if year is None and periods:
            year, month = periods[0]
        rows = conn.execute("""SELECT e.exchange_id,s.src_code,p.name,p.process_type,
                   f.name,f.product_type,pf.direction,e.amount::text,u.symbol
            FROM lci_exchange e JOIN source s USING(source_id)
            JOIN process_flow pf USING(process_flow_id) JOIN process p USING(process_id)
            JOIN flow f USING(flow_id) JOIN unit u USING(unit_id)
            WHERE e.period_year=%s AND e.period_month=%s AND e.validation_status='VERIFIED'
              AND ((s.src_code=ANY(%s) AND f.product_type=%s AND pf.direction='IN')
                OR (f.product_type=%s AND pf.direction='OUT' AND p.process_type IN ('PRODUCTION','EXPORT','DISTRIBUTION'))
                OR (f.name=%s AND p.process_type='EMISSION' AND pf.direction='OUT'))
            ORDER BY s.src_code,p.name,f.name,e.exchange_id""",
            (year,month,USE_SOURCES[fuel],FUEL_TYPES[fuel],FUEL_TYPES[fuel],EMISSIONS[fuel])).fetchall()
    result = dict(fuel=fuel,year=year,month=month,periods=[dict(year=y,month=m) for y,m in periods],
                  uses=[],outputs=[],emissions=[])
    for eid, source, process, kind, product, _, direction, amount, unit in rows:
        category = 'emissions' if kind == 'EMISSION' else ('uses' if direction == 'IN' else 'outputs')
        result[category].append(dict(entity_id=eid,source_code=source,process=process,
                                     process_type=kind,product=product,amount=amount,unit=unit))
    return result
