"""Create/update pgvector embeddings for LCI Exchange rows using Gemini."""

import argparse
import json
from math import sqrt
import time

import psycopg
from google import genai
from google.genai import types

from app.config import get_settings


ROWS_SQL = """
SELECT e.exchange_id, s.src_code, s.dataset_name, s.agency,
       p.name, p.process_type, f.name, f.product_type, pf.direction,
       e.amount::text, u.symbol, e.period_year, e.period_month,
       e.validation_status
FROM lci_exchange e
JOIN process_flow pf ON pf.process_flow_id = e.process_flow_id
JOIN process p ON p.process_id = pf.process_id
JOIN flow f ON f.flow_id = pf.flow_id
JOIN unit u ON u.unit_id = e.unit_id
JOIN source s ON s.source_id = e.source_id
LEFT JOIN semantic_search_documents d
       ON d.entity_type = 'exchange' AND d.entity_id = e.exchange_id
WHERE d.document_id IS NULL
   OR d.metadata->>'validation_status' IS DISTINCT FROM e.validation_status
   OR d.metadata->>'amount' IS DISTINCT FROM e.amount::text
   OR d.metadata->>'unit' IS DISTINCT FROM u.symbol
   OR d.metadata->>'process_name' IS DISTINCT FROM p.name
   OR d.metadata->>'process_type' IS DISTINCT FROM p.process_type
   OR d.metadata->>'flow_name' IS DISTINCT FROM f.name
   OR d.metadata->>'product_type' IS DISTINCT FROM f.product_type
   OR d.metadata->>'direction' IS DISTINCT FROM pf.direction
   OR d.metadata->>'period_year' IS DISTINCT FROM e.period_year::text
   OR d.metadata->>'period_month' IS DISTINCT FROM e.period_month::text
   OR d.metadata->>'dataset_name' IS DISTINCT FROM s.dataset_name
ORDER BY e.exchange_id
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--limit", type=int, default=0, help="index only the first N rows; 0 means all pending/changed rows")
    parser.add_argument("--pause", type=float, default=0.2, help="seconds between Gemini embedding batches")
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 100:
        parser.error("--batch-size must be between 1 and 100")

    settings = get_settings()
    ai = genai.Client(api_key=settings.gemini_api_key)
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute(ROWS_SQL).fetchall()
        if args.limit:
            rows = rows[:args.limit]
        print(f"Rows needing embeddings: {len(rows):,}", flush=True)

        for start in range(0, len(rows), args.batch_size):
            batch = rows[start : start + args.batch_size]
            documents = []
            for row in batch:
                (exchange_id, src_code, dataset_name, agency, process_name,
                 process_type, flow_name, product_type, direction, amount,
                 unit, year, month, validation_status) = row
                period = f"{year}-{month:02d}" if month else str(year)
                title = f"{src_code}: {flow_name} / {process_name} / {period}"
                content = (
                    f"LCI exchange. Source {src_code}, dataset {dataset_name}, agency {agency}. "
                    f"Process {process_name}, type {process_type}. Flow/product {flow_name}, "
                    f"product type {product_type}, direction {direction}. Amount {amount} {unit}. "
                    f"Period {period}. Validation status {validation_status}. "
                    f"รายการ LCI จากแหล่ง {src_code} ชุดข้อมูล {dataset_name}. "
                    f"กระบวนการ {process_name} ประเภท {process_type}. ผลิตภัณฑ์หรือการไหล {flow_name}. "
                    f"ปริมาณ {amount} {unit} ช่วงเวลา {period}."
                )
                documents.append((exchange_id, src_code, title, content, {
                    "dataset_name": dataset_name,
                    "process_name": process_name,
                    "process_type": process_type,
                    "flow_name": flow_name,
                    "product_type": product_type,
                    "direction": direction,
                    "amount": amount,
                    "unit": unit,
                    "period_year": year,
                    "period_month": month,
                    "validation_status": validation_status,
                }))

            response = ai.models.embed_content(
                model=settings.gemini_embedding_model,
                contents=[doc[3] for doc in documents],
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=settings.embedding_dimensions,
                ),
            )
            if not response.embeddings or len(response.embeddings) != len(documents):
                raise RuntimeError("Gemini returned an unexpected number of embeddings")

            values = []
            for doc, embedded in zip(documents, response.embeddings):
                vector = embedded.values
                if vector is None or len(vector) != settings.embedding_dimensions:
                    raise RuntimeError("Gemini embedding dimensions do not match the database schema")
                norm = sqrt(sum(value * value for value in vector))
                if not norm:
                    raise RuntimeError("Gemini returned a zero vector")
                vector = [value / norm for value in vector]
                vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
                values.append((doc[0], doc[1], doc[2], doc[3], json.dumps(doc[4]), vector_literal))

            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO semantic_search_documents
                        (entity_type, entity_id, title, content, source_code, metadata, embedding, indexed_at)
                    VALUES ('exchange', %s, %s, %s, %s, %s::jsonb, %s::vector, now())
                    ON CONFLICT (entity_type, entity_id) DO UPDATE
                    SET title = EXCLUDED.title, content = EXCLUDED.content,
                        source_code = EXCLUDED.source_code, metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding, indexed_at = now()
                    """,
                    values,
                )
            conn.commit()
            done = min(start + len(batch), len(rows))
            print(f"Indexed {done:,}/{len(rows):,}", flush=True)
            if args.pause and done < len(rows):
                time.sleep(args.pause)

    print("Indexing complete")


if __name__ == "__main__":
    main()
