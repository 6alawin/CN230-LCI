"""Monthly coal inputs to electricity processes, read directly from verified exchanges."""
import re

import psycopg
from psycopg import sql

MONTHS = "มกราคม กุมภาพันธ์ มีนาคม เมษายน พฤษภาคม มิถุนายน กรกฎาคม สิงหาคม กันยายน ตุลาคม พฤศจิกายน ธันวาคม".split()


def monthly_scope(query, years):
    text = query.casefold()
    if len(years) != 1 or not any(word in text for word in ("ไฟฟ้า", "electricity", "power generation")):
        return None
    if any(word in text for word in ("ปล่อย", "คาร์บอน", "co2", "co₂", "emission", "นำเข้า", "ส่งออก", "เทียบ", "เปรียบ", "เฉลี่ย", "สูงสุด", "ต่ำสุด", "ก๊าซ", "น้ำมัน", "kwh", "gwh", "mwh", "หน่วยไฟ")):
        return None
    if not any(word in text for word in ("การใช้", "ใช้ถ่าน", "ใช้ลิกไนต์", "ใช้เชื้อเพลิง", "consumption", "used", "fuel use")):
        return None
    months = [i for i, name in enumerate(MONTHS, 1) if name in text]
    if not months and not any(word in text for word in ("ทุกเดือน", "รายเดือน", "แต่ละเดือน", "monthly", "each month", "every month")):
        return None
    fuels = []
    if "ถ่านหิน" in text or "coal" in text:
        fuels.append("COAL")
    if "ลิกไนต์" in text or "lignite" in text:
        fuels.append("LIGNITE")
    if not fuels:
        return None
    plants = [name for name in ("IPP", "SPP", "EGAT") if re.search(r"\b" + name + r"\b", query, re.I | re.ASCII)]
    if "กฟผ" in text and "EGAT" not in plants:
        plants.append("EGAT")
    return months or list(range(1, 13)), fuels, plants


def monthly_report(request, settings, year, scope):
    months, fuels, plants = scope
    schema = sql.Identifier(settings.cloud_snapshot_schema)
    statement = sql.SQL("""
        SELECT e.period_month, s.src_code, p.name, f.name, e.amount, u.symbol, e.exchange_id
        FROM {s}.lci_exchange e
        JOIN {s}.source s USING (source_id)
        JOIN {s}.unit u USING (unit_id)
        JOIN {s}.process_flow pf USING (process_flow_id)
        JOIN {s}.process p USING (process_id)
        JOIN {s}.flow f USING (flow_id)
        WHERE e.period_year = %s AND e.period_month = ANY(%s)
          AND e.validation_status = 'VERIFIED' AND pf.direction = 'IN'
          AND p.process_type = 'DOMESTIC_USE' AND p.name LIKE 'ELECTRICITY (%%)'
          AND upper(f.name) = ANY(%s) AND (%s::text IS NULL OR s.src_code = %s)
          AND (%s::text[] IS NULL OR p.name = ANY(%s))
        ORDER BY e.period_month, s.src_code, p.name, f.name, e.exchange_id
    """).format(s=schema)
    names = [f"ELECTRICITY ({plant})" for plant in plants] or None
    with psycopg.connect(settings.database_url, connect_timeout=15) as conn:
        rows = conn.execute(statement, (year, months, fuels, request.source_code, request.source_code, names, names)).fetchall()
    records = []
    by_month = {month: [] for month in months}
    for month, source, process, fuel, amount, unit, exchange in rows:
        value = format(amount.normalize(), "f")
        plant = process.removeprefix("ELECTRICITY ").strip("()")
        label = f"{plant} {fuel} {value} {unit} [{source} / {exchange}]"
        by_month[month].append(label)
        records.append(dict(entity_type="exchange", entity_id=exchange, source_code=source,
                            title=f"{year}-{month:02} · {plant} · {fuel}", content=label))
    found = sum(bool(values) for values in by_month.values())
    lines = [f"ปริมาณเชื้อเพลิงที่ใช้ผลิตไฟฟ้าปี {year} พบข้อมูล {found}/{len(months)} เดือนตามเงื่อนไข"]
    lines.extend(f"{MONTHS[m-1]} · " + (" | ".join(values) or "ไม่มีรายการตามเงื่อนไข") for m, values in by_month.items())
    return dict(query=request.query, backend="monthly_sql", year_filter=[year], answer="\n".join(lines),
                results=records[:request.limit], total_records=len(records))
