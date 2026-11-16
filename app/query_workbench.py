"""Bounded, read-only SQL results for the query page."""

import re

import psycopg
from psycopg import sql


def run_sql(database_url: str, statement: str, schema: str = "public") -> dict:
    query = statement.strip().rstrip(";").strip()
    if not re.match(r"^(SELECT|WITH)\b", query, re.IGNORECASE):
        raise ValueError("รองรับเฉพาะคำสั่ง SELECT หรือ WITH สำหรับอ่านข้อมูล")
    if ";" in query:
        raise ValueError("กรุณาส่งครั้งละหนึ่งคำสั่ง")
    with psycopg.connect(database_url, connect_timeout=8) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '5000ms'")
        conn.execute(sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema)))
        with conn.cursor() as cursor:
            cursor.execute(query)
            if cursor.description is None:
                raise ValueError("คำสั่งต้องคืนผลลัพธ์เป็นตาราง")
            columns = [column.name for column in cursor.description]
            rows = cursor.fetchmany(101)
    return {"columns": columns, "rows": [[str(value) if value is not None else None for value in row]
                                       for row in rows[:100]], "truncated": len(rows) > 100}
