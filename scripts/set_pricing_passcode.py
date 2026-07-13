"""Set the passcode that unlocks Prices in the driver app.

Run from server-side (venv active):

  python -m scripts.set_pricing_passcode
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import text

from scripts._bootstrap import bootstrap, db_engine


def normalize_code(raw: str) -> str:
    return re.sub(r"\D", "", raw)[:4]


def main() -> int:
    bootstrap()
    code = normalize_code(input("Prices passcode (4 digits): "))

    if not re.fullmatch(r"\d{4}", code):
        print("Passcode must be exactly 4 digits.")
        return 1

    try:
        with db_engine() as engine:
            with engine.connect() as conn:
                tables = {
                    row[0]
                    for row in conn.execute(text("SHOW TABLES")).fetchall()
                }
                if "pricing_passcode" not in tables:
                    print(
                        "Table pricing_passcode is missing. "
                        "Run: python -m alembic upgrade head"
                    )
                    return 1

                now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                conn.execute(
                    text(
                        """
                        INSERT INTO pricing_passcode (id, code, updated_at)
                        VALUES ('default', :code, :updated_at)
                        ON DUPLICATE KEY UPDATE
                            code = VALUES(code),
                            updated_at = VALUES(updated_at)
                        """
                    ),
                    {"code": code, "updated_at": now},
                )
                conn.commit()
                print(f"Pricing passcode set: {code}")
                print("Drivers must enter this code to open Prices in the app.")
    except Exception as error:
        print(error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
