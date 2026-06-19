"""Set a 4-digit driver verification code. Run: python -m scripts.set_driver_verification_code"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import text

from scripts._bootstrap import bootstrap, db_engine


def normalize_code(raw: str) -> str:
    return re.sub(r"\D", "", raw)[:4]


def main() -> int:
    bootstrap()
    email = input("Driver email: ").strip().lower()
    code = normalize_code(input("4-digit verification code: "))

    if not email:
        print("Driver email is required.")
        return 1
    if not re.fullmatch(r"\d{4}", code):
        print("Code must be exactly 4 digits.")
        return 1

    try:
        with db_engine() as engine:
            with engine.connect() as conn:
                driver = conn.execute(
                    text(
                        """
                        SELECT id, email, name
                        FROM `Driver`
                        WHERE email = :email
                        LIMIT 1
                        """
                    ),
                    {"email": email},
                ).mappings().first()
                if not driver:
                    print(f"No driver account found for: {email}")
                    return 1

                existing_by_code = conn.execute(
                    text(
                        """
                        SELECT driver_id
                        FROM driver_verification_codes
                        WHERE code = :code
                        LIMIT 1
                        """
                    ),
                    {"code": code},
                ).mappings().first()
                if existing_by_code and existing_by_code["driver_id"] != driver["id"]:
                    print("That code is already assigned to another driver.")
                    return 1

                conn.execute(
                    text(
                        """
                        INSERT INTO driver_verification_codes (
                            id, driver_id, code, is_active, created_at, updated_at
                        ) VALUES (
                            :id, :driver_id, :code, 1, NOW(3), NOW(3)
                        )
                        ON DUPLICATE KEY UPDATE
                            code = VALUES(code),
                            is_active = 1,
                            updated_at = NOW(3)
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "driver_id": driver["id"],
                        "code": code,
                    },
                )
                conn.commit()
                print(
                    f"Verification code set for {driver['name']} <{driver['email']}>: {code}"
                )
    except Exception as error:
        print(error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
