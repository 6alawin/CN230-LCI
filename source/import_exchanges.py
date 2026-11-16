"""งาน: นำเข้าข้อมูลจำนวนมากจาก CSV ไปยัง PROCESS, FLOW, PROCESS_FLOW และ LCI_EXCHANGE
ใช้แทนการเขียน INSERT รายแถว โดยเก็บ source_id, หน่วย และช่วงเวลาของข้อมูลต้นทาง
PROCESS.name เก็บเฉพาะบริบทที่สั้น เช่น SIRIKIT, INDUSTRY หรือ NATIONAL.
"""

from __future__ import annotations

import csv
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg


SOURCE_DIR = Path(__file__).resolve().parent
BATCH_SIZE = 1000
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# CSV column -> relational model mapping follows each SRC definition in the SRS.
FIXED_CONFIG = {
    "SRC-01": ("Source", "Crude oil", "OIL", "Quantity", "UNIT"),
    "SRC-02": ("Source", "Condensate", "OIL", "Quantity", "UNIT"),
    "SRC-03": ("Source", "Crude oil", "OIL", "Quantity", "UNIT"),
    "SRC-04": ("Company", "Crude oil", "OIL", "Quantity", "UNIT"),
    "SRC-11": ("Sector", "Natural gas", "NATURAL_GAS", "Quantity", "UNIT"),
    "SRC-12": ("Distribution", "NGL", "NATURAL_GAS", "Quantity", "UNIT"),
    "SRC-16": ("Production of B100", "B100", "BIOFUEL", "Quantity", "UNIT"),
    "SRC-17": ("Production of Ethanol", "Ethanol", "BIOFUEL", "Quantity", "UNIT"),
}

PRODUCT_CONFIG = {
    "SRC-05": ("Product", "PRODUCTION", "OUT", "OIL"),
    "SRC-06": ("Product", "IMPORT", "IN", "OIL"),
    "SRC-07": ("Product", "EXPORT", "OUT", "OIL"),
    "SRC-08": ("Product", "DOMESTIC_USE", "IN", "OIL"),
}

EXPECTED_UNITS = {
    "BBL/DAY": "VOLUME_RATE",
    "Million Litres": "VOLUME",
    "Million Litres/Day": "VOLUME_RATE",
    "MMSCFD": "GAS_RATE",
    "MMSCF": "VOLUME",
    "Thousand Tons": "MASS",
    "Ton": "MASS",
    "1,000 Tons": "MASS",
    "Thousand Tons-CO2": "MASS",
}


def read_source_rows(src_code: str):
    """Yield (line number, row) while normalizing SRC-14's duplicate UNIT header."""
    path = SOURCE_DIR / f"{src_code}.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        if src_code == "SRC-14":
            reader = csv.reader(stream)
            next(reader, None)
            headers = ["Year", "Month", "Coal Type", "Quantity", "Quantity Unit", "Value", "Value Unit"]
            for line_number, values in enumerate(reader, start=2):
                yield line_number, dict(zip(headers, values))
        else:
            reader = csv.DictReader(stream)
            for line_number, row in enumerate(reader, start=2):
                yield line_number, row


def classify(src_code: str, row: dict[str, str]):
    """Return process name/type, flow name/type, direction, amount, and unit."""
    if src_code == "SRC-22":
        fuel = (row.get('Fuel Type') or '').strip().upper()
        fuels = {'DIESEL OIL': ('DIESEL', 'OIL'), 'FUEL OIL': ('FUEL OIL', 'OIL'),
                 'NATURAL GAS': ('Natural gas', 'NATURAL_GAS'), 'LIGNITE': ('LIGNITE', 'COAL'),
                 'PALM OIL': ('PALM OIL', 'BIOFUEL')}
        if fuel not in fuels:
            raise ValueError(f'unknown EGAT fuel: {fuel}')
        name, kind = fuels[fuel]
        return 'ELECTRICITY (EGAT)', 'DOMESTIC_USE', name, kind, 'IN', row.get('Quantity'), row.get('UNIT')
    if src_code in FIXED_CONFIG:
        category_column, flow_name, product_type, amount_column, unit_column = FIXED_CONFIG[src_code]
        category = (row.get(category_column) or "").strip()
        if not category:
            raise ValueError(f"missing {category_column}")

        if src_code in ("SRC-01", "SRC-02"):
            process_type, direction = "PRODUCTION", "OUT"
            process_name = category
        elif src_code == "SRC-03":
            process_type, direction = "IMPORT", "IN"
            process_name = category
        elif src_code == "SRC-04":
            process_type, direction = "REFINING", "IN"
            process_name = category
        elif src_code == "SRC-11":
            process_type, direction = "DOMESTIC_USE", "IN"
            process_name = category
        elif src_code == "SRC-12":
            if category.upper() == "EXPORT":
                process_type, direction = "EXPORT", "OUT"
            else:
                process_type, direction = "DISTRIBUTION", "OUT"
            process_name = category
        else:
            process_type, direction = "PRODUCTION", "OUT"
            process_name = "NATIONAL"

        amount = row.get(amount_column)
        unit = row.get(unit_column)
        return process_name, process_type, flow_name, product_type, direction, amount, unit

    if src_code in PRODUCT_CONFIG:
        category_column, process_type, direction, product_type = PRODUCT_CONFIG[src_code]
        flow_name = (row.get(category_column) or "").strip()
        if not flow_name:
            raise ValueError(f"missing {category_column}")
        return "NATIONAL", process_type, flow_name, product_type, direction, row.get("Quantity"), row.get("UNIT")

    if src_code == "SRC-09":
        category = (row.get("Supply & Demand") or "").strip()
        category_upper = category.upper()
        if category_upper.startswith("PRODUCTION"):
            process_type, direction = "PRODUCTION", "OUT"
        elif category_upper == "IMPORT":
            process_type, direction = "IMPORT", "IN"
        elif category_upper == "EXPORT":
            process_type, direction = "EXPORT", "OUT"
        elif category_upper.startswith("CONSUMPTION"):
            process_type, direction = "DOMESTIC_USE", "IN"
        else:
            raise ValueError(f"unknown LPG category: {category}")
        context = category.partition("(")[2].rstrip(")").strip() or "NATIONAL"
        return context, process_type, "LPG", "OIL", direction, row.get("Quantity"), row.get("UNIT")

    if src_code == "SRC-10":
        category = (row.get("Source") or "").strip()
        process_type = "IMPORT" if category.upper() in {"LNG", "YADANA", "ZAWTIKA"} else "PRODUCTION"
        direction = "IN" if process_type == "IMPORT" else "OUT"
        return category, process_type, "Natural gas", "NATURAL_GAS", direction, row.get("Quantity"), row.get("UNIT")

    if src_code == "SRC-13":
        category = (row.get("Production&Consumption") or "").strip()
        category_upper = category.upper()
        if category_upper.startswith("PRODUCTION"):
            process_type, direction = "PRODUCTION", "OUT"
        elif category_upper.startswith("CONSUMPTION"):
            process_type, direction = "DOMESTIC_USE", "IN"
        else:
            raise ValueError(f"unknown lignite category: {category}")
        context = category.partition("(")[2].rstrip(")").strip() or "NATIONAL"
        return context, process_type, "LIGNITE", "COAL", direction, row.get("Quantity"), row.get("UNIT")

    if src_code == "SRC-14":
        category = (row.get("Coal Type") or "").strip()
        if category.upper() == "TOTAL":
            raise ValueError("aggregate TOTAL row excluded to avoid double counting")
        return "NATIONAL", "IMPORT", category, "COAL", "IN", row.get("Quantity"), row.get("Quantity Unit")

    if src_code == "SRC-15":
        product = (row.get("Type") or "").strip()
        sector = (row.get("Sector") or "").strip()
        flow_name = product.upper()
        return sector.upper(), "DOMESTIC_USE", flow_name, "COAL", "IN", row.get("Value"), row.get("UNIT")

    if src_code in ("SRC-18", "SRC-19", "SRC-20", "SRC-21"):
        fuel = (row.get("Fuel Type") or "").strip()
        flow_name = f"CO2 - {fuel}"
        sector = {"SRC-18": "OTHER ECONOMIC SECTORS", "SRC-19": "INDUSTRY", "SRC-20": "TRANSPORT", "SRC-21": "ELECTRICITY GENERATION"}[src_code]
        return sector, "EMISSION", flow_name, "EMISSION", "OUT", row.get("Quantity"), row.get("UNIT")

    raise ValueError(f"no mapping configured for {src_code}")


def parse_exchange(src_code: str, line_number: int, row: dict[str, str]):
    process_name, process_type, flow_name, product_type, direction, raw_amount, raw_unit = classify(src_code, row)
    unit = (raw_unit or "").strip()
    if unit not in EXPECTED_UNITS:
        raise ValueError(f"unsupported source unit: {unit!r}")
    amount_text = (raw_amount or "").strip().replace(",", "")
    if not amount_text:
        raise ValueError("missing amount")
    try:
        amount = Decimal(amount_text)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount: {raw_amount!r}") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"amount must be a non-negative finite number: {raw_amount!r}")

    try:
        year = int((row.get("Year") or "").strip())
        month = MONTHS[(row.get("Month") or "").strip().lower()]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"invalid year/month: {row.get('Year')!r}/{row.get('Month')!r}") from exc

    return {
        "src_code": src_code,
        "line_number": line_number,
        "process_name": process_name,
        "process_type": process_type,
        "flow_name": flow_name,
        "product_type": product_type,
        "direction": direction,
        "amount": amount,
        "unit": unit,
        "year": year,
        "month": month,
        "note": f"Imported from { {'SRC-18': 'dataset_11_65', 'SRC-19': 'dataset_11_64', 'SRC-20': 'dataset_11_63', 'SRC-21': 'dataset_11_62', 'SRC-22': 'dataset_11_31'}.get(src_code, src_code) }.csv row {line_number}",
    }


def main() -> None:
    parsed_rows: list[dict] = []
    issues: list[dict] = []
    source_codes = [f"SRC-{i:02d}" for i in range(1, 23)]

    for src_code in source_codes:
        path = SOURCE_DIR / f"{src_code}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Required source file is missing: {path}")
        for line_number, row in read_source_rows(src_code):
            try:
                parsed_rows.append(parse_exchange(src_code, line_number, row))
            except ValueError as exc:
                reason = str(exc)
                status = "SKIPPED" if reason.startswith("aggregate TOTAL row excluded") else "ERROR"
                issues.append({
                    "src_code": src_code,
                    "line_number": line_number,
                    "status": status,
                    "reason": reason,
                    "raw_data": row,
                })

    for status, filename in (("ERROR", "exchange_import_errors.csv"), ("SKIPPED", "exchange_import_skipped.csv")):
        with (SOURCE_DIR / filename).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["src_code", "line_number", "status", "reason", "raw_data"])
            writer.writeheader()
            for issue in issues:
                if issue["status"] == status:
                    writer.writerow({
                        **issue,
                        "raw_data": json.dumps(issue["raw_data"], ensure_ascii=False),
                    })

    connection_settings = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5433")),
        "dbname": os.getenv("DB_NAME", "cn230lci"),
        "user": os.getenv("DB_USER", "cn230lci"),
        "password": os.getenv("DB_PASSWORD", "portugalsql"),
    }

    with psycopg.connect(**connection_settings) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT location_id FROM location WHERE country = 'Thailand'")
            location_row = cur.fetchone()
            if location_row is None:
                raise RuntimeError("Thailand is missing; run query/insert_location.sql first")
            location_id = location_row[0]

            cur.execute("SELECT unit_id, symbol FROM unit")
            unit_ids = {symbol: unit_id for unit_id, symbol in cur.fetchall()}
            missing_units = set(EXPECTED_UNITS) - set(unit_ids)
            if missing_units:
                raise RuntimeError(f"Missing units; run query/insert_units.sql first: {sorted(missing_units)}")

            cur.execute("SELECT source_id, src_code FROM source")
            source_ids = {src_code: source_id for source_id, src_code in cur.fetchall()}
            missing_sources = set(source_codes) - set(source_ids)
            if missing_sources:
                raise RuntimeError(f"Missing source rows; run query/insert_sources.sql first: {sorted(missing_sources)}")

            imported_source_ids = [source_ids[src_code] for src_code in source_codes]
            cur.execute(
                "UPDATE lci_import_log SET resolved_at = now() "
                "WHERE source_id = ANY(%s) AND resolved_at IS NULL",
                (imported_source_ids,),
            )
            issue_values = [
                (
                    source_ids[issue["src_code"]],
                    issue["line_number"],
                    issue["status"],
                    issue["reason"],
                    json.dumps(issue["raw_data"], ensure_ascii=False),
                )
                for issue in issues
            ]
            if issue_values:
                cur.executemany(
                    """
                    INSERT INTO lci_import_log
                        (source_id, source_line, status, reason, raw_data)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (source_id, source_line) DO UPDATE
                    SET status = EXCLUDED.status,
                        reason = EXCLUDED.reason,
                        raw_data = EXCLUDED.raw_data,
                        last_seen_at = now(),
                        resolved_at = NULL
                    """,
                    issue_values,
                )

            process_types: set[tuple[str, str]] = set()
            flow_types: dict[str, str] = {}
            for item in parsed_rows:
                process_types.add((item["process_name"], item["process_type"]))
                flow_types[item["flow_name"]] = item["product_type"]

            process_ids: dict[tuple[str, str], int] = {}
            for process_name, process_type in process_types:
                cur.execute(
                    """
                    INSERT INTO process (name, process_type, location_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name, process_type, location_id) DO NOTHING
                    RETURNING process_id
                    """,
                    (process_name, process_type, location_id),
                )
                result = cur.fetchone()
                if result is None:
                    cur.execute(
                        """
                        SELECT process_id FROM process
                        WHERE name = %s AND process_type = %s AND location_id = %s
                        """,
                        (process_name, process_type, location_id),
                    )
                    result = cur.fetchone()
                process_ids[(process_name, process_type)] = result[0]

            flow_ids: dict[str, int] = {}
            for flow_name, product_type in flow_types.items():
                cur.execute(
                    """
                    INSERT INTO flow (name, product_type)
                    VALUES (%s, %s)
                    ON CONFLICT (name) DO UPDATE
                    SET product_type = EXCLUDED.product_type
                    RETURNING flow_id
                    """,
                    (flow_name, product_type),
                )
                flow_ids[flow_name] = cur.fetchone()[0]

            process_flow_ids: dict[tuple[str, str, str], int] = {}
            pair_directions: dict[tuple[str, str, str], str] = {}
            for item in parsed_rows:
                key = (item["process_name"], item["process_type"], item["flow_name"])
                pair_directions[key] = item["direction"]
            for (process_name, process_type, flow_name), direction in pair_directions.items():
                cur.execute(
                    """
                    INSERT INTO process_flow (process_id, flow_id, direction)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (process_id, flow_id) DO UPDATE
                    SET direction = EXCLUDED.direction
                    RETURNING process_flow_id
                    """,
                    (process_ids[(process_name, process_type)], flow_ids[flow_name], direction),
                )
                process_flow_ids[(process_name, process_type, flow_name)] = cur.fetchone()[0]

            cur.execute(
                """
                CREATE TEMP TABLE stage_exchange (
                    import_key text PRIMARY KEY,
                    process_flow_id integer NOT NULL,
                    amount numeric(24, 8) NOT NULL,
                    unit_id integer NOT NULL,
                    period_year integer NOT NULL,
                    period_month integer,
                    source_id integer NOT NULL,
                    note text NOT NULL
                ) ON COMMIT DROP
                """
            )

            stage_sql = """
                INSERT INTO stage_exchange
                    (import_key, process_flow_id, amount, unit_id,
                     period_year, period_month, source_id, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (import_key) DO NOTHING
            """
            for start in range(0, len(parsed_rows), BATCH_SIZE):
                batch = parsed_rows[start : start + BATCH_SIZE]
                values = [
                    (
                        f"{item['src_code']}:{item['line_number']}",
                        process_flow_ids[(item["process_name"], item["process_type"], item["flow_name"])],
                        item["amount"],
                        unit_ids[item["unit"]],
                        item["year"],
                        item["month"],
                        source_ids[item["src_code"]],
                        item["note"],
                    )
                    for item in batch
                ]
                cur.executemany(stage_sql, values)

            cur.execute(
                """
                INSERT INTO lci_exchange
                    (process_flow_id, amount, unit_id, period_year,
                     period_month, source_id, validation_status, note)
                SELECT stage.process_flow_id, stage.amount, stage.unit_id,
                       stage.period_year, stage.period_month, stage.source_id,
                       'PENDING', stage.note
                FROM stage_exchange AS stage
                WHERE NOT EXISTS (
                    SELECT 1 FROM lci_exchange AS existing
                    WHERE existing.note = stage.note
                )
                """
            )
            inserted = cur.rowcount

    error_count = sum(issue["status"] == "ERROR" for issue in issues)
    skipped_count = sum(issue["status"] == "SKIPPED" for issue in issues)
    print(f"Parsed source rows: {len(parsed_rows) + len(issues)}")
    print(f"Valid exchange rows: {len(parsed_rows)}")
    print(f"Inserted new exchanges: {inserted}")
    print(f"Rows logged as ERROR: {error_count}")
    print(f"Rows intentionally skipped: {skipped_count}")
    if error_count:
        print(f"Review: {SOURCE_DIR / 'exchange_import_errors.csv'}")
    if skipped_count:
        print(f"Skipped rows: {SOURCE_DIR / 'exchange_import_skipped.csv'}")


if __name__ == "__main__":
    main()
