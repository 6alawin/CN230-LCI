"""Apply the additive pgvector schema for semantic search."""

from pathlib import Path

import psycopg

from app.config import get_settings


def main() -> None:
    migration = Path(__file__).resolve().parents[1] / "db" / "001_semantic_search.sql"
    statements = [part.strip() for part in migration.read_text(encoding="utf-8").split(";")]
    statements = [statement for statement in statements if statement]

    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        for statement in statements:
            conn.execute(statement)

    print(f"Applied {len(statements)} semantic-search schema statements.", flush=True)


if __name__ == "__main__":
    main()
