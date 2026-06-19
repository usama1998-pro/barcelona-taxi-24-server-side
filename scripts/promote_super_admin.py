"""Promotes an existing staff admin to super admin. Run: python -m scripts.promote_super_admin"""

from __future__ import annotations

from sqlalchemy import text

from scripts._bootstrap import bootstrap, db_engine


def main() -> int:
    bootstrap()
    email = input("Staff user email (must be is_admin): ").strip().lower()
    if not email:
        print("Email is required.")
        return 1

    try:
        with db_engine() as engine:
            with engine.connect() as conn:
                user = conn.execute(
                    text(
                        """
                        SELECT id, email, is_admin, is_super_admin
                        FROM `User`
                        WHERE email = :email
                        LIMIT 1
                        """
                    ),
                    {"email": email},
                ).mappings().first()

                if not user:
                    print("No user with that email.")
                    return 1
                if not user["is_admin"]:
                    print("That user is not a staff admin (is_admin is false).")
                    return 1
                if user["is_super_admin"]:
                    print(f"Already super admin: {user['email']}")
                    return 0

                conn.execute(
                    text("UPDATE `User` SET is_super_admin = 1 WHERE id = :id"),
                    {"id": user["id"]},
                )
                conn.commit()
                print(f"Promoted to super admin: {user['email']}")
    except Exception as error:
        print(error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
