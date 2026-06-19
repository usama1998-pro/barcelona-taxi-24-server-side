"""Truncates all base tables. Run: FLUSH_ALL_CONFIRM=YES_FLUSH python -m scripts.flush_db"""

from __future__ import annotations

import os

from sqlalchemy import text

from scripts._bootstrap import bootstrap, db_engine

REQUIRED_CONFIRMATION = "YES_FLUSH"


def main() -> int:
    bootstrap()
    confirmation = os.getenv("FLUSH_ALL_CONFIRM")
    if confirmation != REQUIRED_CONFIRMATION:
        print(
            f"Refusing to flush DB. Set FLUSH_ALL_CONFIRM={REQUIRED_CONFIRMATION} to proceed."
        )
        return 1

    with db_engine() as engine:
        with engine.connect() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            rows = conn.execute(
                text(
                    """
                    SELECT TABLE_NAME AS table_name
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_TYPE = 'BASE TABLE'
                    """
                )
            ).mappings().all()

            for row in rows:
                table_name = row["table_name"].replace("`", "``")
                conn.execute(text(f"TRUNCATE TABLE `{table_name}`"))

            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            conn.commit()

    print("All base tables truncated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
