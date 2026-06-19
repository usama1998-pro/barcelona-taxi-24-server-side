"""Set a 4-digit verification code for a staff admin. Run: python -m scripts.set_admin_code"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import text

from scripts._bootstrap import bootstrap, db_engine


def normalize_code(raw: str) -> str:
    return re.sub(r"\D", "", raw)[:4]


def main() -> int:
    bootstrap()
    email = input("Admin email: ").strip().lower()
    code = normalize_code(input("4-digit code: "))

    if not email:
        print("Admin email is required.")
        return 1
    if not re.fullmatch(r"\d{4}", code):
        print("Code must be exactly 4 digits.")
        return 1

    try:
        with db_engine() as engine:
            with engine.connect() as conn:
                user = conn.execute(
                    text(
                        """
                        SELECT id, email, fullName, phone, password, is_admin
                        FROM `User`
                        WHERE email = :email
                        LIMIT 1
                        """
                    ),
                    {"email": email},
                ).mappings().first()

                if not user:
                    print(f"No user found for: {email}")
                    return 1
                if not user["is_admin"]:
                    print("User exists but is not a staff admin (is_admin is false).")
                    return 1

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
                    driver_id = str(uuid.uuid4())
                    conn.execute(
                        text(
                            """
                            INSERT INTO `Driver` (
                                id, user_id, name, email, phone, password,
                                isAvailable, isActive, token_version
                            ) VALUES (
                                :id, :user_id, :name, :email, :phone, :password,
                                1, 1, 0
                            )
                            """
                        ),
                        {
                            "id": driver_id,
                            "user_id": user["id"],
                            "name": user["fullName"],
                            "email": user["email"],
                            "phone": user["phone"],
                            "password": user["password"],
                        },
                    )
                    driver = {"id": driver_id, "email": user["email"], "name": user["fullName"]}
                    print(f"Created linked driver profile for admin {driver['email']}.")

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
                    print("That code is already assigned to another account.")
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
                print(f"Code set for admin {user['email']}: {code}")
    except Exception as error:
        print(error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
