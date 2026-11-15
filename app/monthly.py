"""Monthly fuel use and emissions read from verified exchanges."""
import re
from collections import defaultdict
from decimal import Decimal

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


def emission_scope(query, years):
    """Recognize requests for a monthly CO2 breakdown by fuel and sector."""
    text = query.casefold()
    if len(years) != 1 or not any(word in text for word in ("คาร์บอน", "co2", "co₂")):
        return None
    if not any(word in text for word in ("ปล่อย", "ผลิต", "เกิด", "emission", "จาก")):
        return None
    months = [i for i, name in enumerate(MONTHS, 1) if name in text]
    if not months and not any(word in text for word in ("ทุกเดือน", "รายเดือน", "แต่ละเดือน", "monthly", "ทั้งปี", "แยกรายสาขา")):
        return None
    fuels = []
    for label, words in (("OIL", ("น้ำมัน", "oil")),
                         ("COAL / LIGNITE", ("ถ่านหิน", "ลิกไนต์", "coal", "lignite")),
                         ("NATURAL GAS", ("ก๊าซธรรมชาติ", "natural gas"))):
        if any(word in text for word in words):
            fuels.append("CO2 - " + label)
    if not fuels:
        return None
    sectors = []
    for name, words in (("INDUSTRY", ("อุตสาหกรรม", "industry")),
                        ("TRANSPORT", ("ขนส่ง", "transport")),
                        ("ELECTRICITY GENERATION", ("ผลิตไฟฟ้า", "ไฟฟ้า", "electricity")),
                        ("OTHER ECONOMIC SECTORS", ("เศรษฐกิจอื่น", "อื่น ๆ", "other economic"))):
        if any(word in text for word in words):
            sectors.append(name)
    return months or list(range(1, 13)), fuels, sectors


def emission_report(request, settings, year, scope):
    months, fuels, sectors = scope
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
          AND e.validation_status = 'VERIFIED' AND pf.direction = 'OUT'
          AND p.process_type = 'EMISSION' AND upper(f.name) = ANY(%s)
          AND (%s::text IS NULL OR s.src_code = %s)
          AND (%s::text[] IS NULL OR p.name = ANY(%s))
        ORDER BY e.period_month, p.name, f.name, e.exchange_id
    """).format(s=schema)
    chosen = sectors or None
    with psycopg.connect(settings.database_url, connect_timeout=15) as conn:
        rows = conn.execute(statement, (year, months, fuels, request.source_code,
                                        request.source_code, chosen, chosen)).fetchall()
    by_month = {month: [] for month in months}
    records = []
    totals = defaultdict(lambda: [Decimal(0), set()])
    for month, source, sector, fuel, amount, unit, exchange in rows:
        label = f"{sector} · {fuel} · {format(amount.normalize(), 'f')} {unit} [{source} / exchange {exchange}]"
        by_month[month].append(label)
        totals[(sector, fuel, unit)][0] += amount
        totals[(sector, fuel, unit)][1].add(month)
        records.append(dict(entity_type="exchange", entity_id=exchange, source_code=source,
                            title=f"{year}-{month:02} · {sector} · {fuel}", content=label))
    found = sum(bool(values) for values in by_month.values())
    lines = [f"การปล่อย CO₂ ปี {year} พบข้อมูล {found}/{len(months)} เดือนตามเงื่อนไข"]
    for (sector, fuel, unit), (amount, observed_months) in sorted(totals.items()):
        coverage = "ครบ 12 เดือน" if len(months) == 12 and len(observed_months) == 12 else f"เฉพาะ {len(observed_months)} เดือนที่มีข้อมูล"
        lines.append(f"รวม {sector} · {fuel} · {format(amount.normalize(), 'f')} {unit} ({coverage})")
    lines.extend(f"{MONTHS[month-1]} · " + (" | ".join(values) or "ไม่มีรายการตามเงื่อนไข")
                 for month, values in by_month.items())
    if len(months) == 12 and found < 12:
        lines.append("ข้อมูลรายเดือนยังไม่ครบ 12 เดือน จึงยังไม่สรุปยอดทั้งปี")
    return dict(query=request.query, backend="monthly_sql", year_filter=[year],
                answer="\n".join(lines), results=records[:request.limit], total_records=len(records))


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
