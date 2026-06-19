"""Creates a staff admin user. Run: python -m scripts.create_admin"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.lib.ensure_super_admin import hash_password
from scripts._bootstrap import bootstrap, db_engine


def main() -> int:
    bootstrap()

    full_name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()
    phone = input("Phone: ").strip()
    password = input("Password (min 8 chars): ").strip()
    password2 = input("Password (again): ").strip()
    super_raw = input(
        "Super admin? (y/N — super admins manage driver verification codes): "
    ).strip().lower()
    is_super_admin = super_raw in {"y", "yes"}

    if not full_name or not email or not phone or not password:
        print("All fields are required.")
        return 1
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return 1
    if password != password2:
        print("Passwords do not match.")
        return 1

    try:
        with db_engine() as engine:
            with engine.connect() as conn:
                driver = conn.execute(
                    text("SELECT id FROM `Driver` WHERE email = :email LIMIT 1"),
                    {"email": email},
                ).first()
                if driver:
                    print(
                        "That email is already used by a driver account; "
                        "choose another email for admin."
                    )
                    return 1

                existing_email = conn.execute(
                    text("SELECT id FROM `User` WHERE email = :email LIMIT 1"),
                    {"email": email},
                ).first()
                if existing_email:
                    print(
                        "That email is already used by a staff user. "
                        "Use a different email or update the existing user in the database."
                    )
                    return 1

                existing_phone = conn.execute(
                    text(
                        "SELECT id, email FROM `User` WHERE phone = :phone LIMIT 1"
                    ),
                    {"phone": phone},
                ).mappings().first()
                if existing_phone:
                    print(
                        "That phone number is already used by staff user "
                        f"{existing_phone['email']} (id: {existing_phone['id']}). "
                        "Use a different phone or change the existing row."
                    )
                    return 1

                user_id = str(uuid.uuid4())
                conn.execute(
                    text(
                        """
                        INSERT INTO `User` (
                            id, fullName, email, phone, password,
                            is_admin, is_super_admin, token_version, createdAt
                        ) VALUES (
                            :id, :full_name, :email, :phone, :password,
                            1, :is_super_admin, 0, NOW(3)
                        )
                        """
                    ),
                    {
                        "id": user_id,
                        "full_name": full_name,
                        "email": email,
                        "phone": phone,
                        "password": hash_password(password),
                        "is_super_admin": 1 if is_super_admin else 0,
                    },
                )
                conn.commit()
                suffix = " [super admin]" if is_super_admin else ""
                print(f"Admin user created: {user_id} ({email}){suffix}.")
    except IntegrityError as error:
        print(
            "Unique constraint failed. Email and phone must be unused on both "
            f"User and Driver tables. ({error.orig})"
        )
        return 1
    except Exception as error:
        print(error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
