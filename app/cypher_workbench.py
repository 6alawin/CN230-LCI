"""Execute bounded Cypher reads with plan classification before execution."""
import json
import os
import re

from neo4j import GraphDatabase, Query, READ_ACCESS
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired


def run_cypher(statement):
    query = statement.strip().rstrip(";").strip()
    if not re.match(r"^(MATCH|OPTIONAL\s+MATCH|WITH|RETURN|UNWIND)\b", query, re.I):
        raise ValueError("รองรับ Cypher สำหรับอ่านข้อมูล เริ่มด้วย MATCH, WITH, RETURN หรือ UNWIND")
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not password:
        raise ValueError("ยังไม่มีค่าการเชื่อม Neo4j Aura บน Service")
    try:
        with GraphDatabase.driver(uri, auth=(user, password), connection_timeout=10,
                                  max_transaction_retry_time=0) as driver:
            with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j"),
                                default_access_mode=READ_ACCESS) as session:
                # ตรวจแผนก่อนรัน เพื่อป้องกันคำสั่งเขียนที่ซ่อนอยู่หลัง MATCH หรือ WITH
                plan = session.run(Query("EXPLAIN " + query, timeout=5)).consume()
                if plan.query_type != "r":
                    raise ValueError("หน้านี้รองรับคำสั่งอ่านข้อมูลเท่านั้น")
                result = session.run(Query(query, timeout=5))
                columns = list(result.keys())
                records = result.fetch(101)
                rows = [[None if v is None else str(v) if isinstance(v, (str, int, float, bool))
                         else json.dumps(v, ensure_ascii=False, default=str)
                         for v in record.data().values()] for record in records[:100]]
                return {"columns": columns, "rows": rows, "truncated": len(records) > 100}
    except (ServiceUnavailable, SessionExpired) as exc:
        raise ValueError("ติดต่อ Neo4j Aura ไม่ได้ กรุณาตรวจสถานะ Instance และค่าการเชื่อมต่อ") from exc
    except Neo4jError as exc:
        raise ValueError("คำสั่ง Cypher ไม่สำเร็จ กรุณาตรวจ syntax และชื่อโหนดกับความสัมพันธ์") from exc
