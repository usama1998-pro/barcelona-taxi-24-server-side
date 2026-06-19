"""
One-time cleanup for legacy Viator guest users.

Dry run (default):
  python -m scripts.cleanup_viator_guest_users

Apply changes:
  python -m scripts.cleanup_viator_guest_users --apply
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import text

from scripts._bootstrap import bootstrap, db_engine

APPLY_FLAG = "--apply"
VIATOR_GUEST_EMAIL_PATTERN = "viator.%@taxibarcelona24.guest"


def resolve_target_staff_user(conn) -> dict[str, str]:
    configured_email = (os.getenv("SUPER_ADMIN_EMAIL") or "").strip().lower()
    if configured_email:
        configured = conn.execute(
            text(
                """
                SELECT id, email, is_admin
                FROM `User`
                WHERE email = :email
                LIMIT 1
                """
            ),
            {"email": configured_email},
        ).mappings().first()
        if configured and configured["is_admin"]:
            return {"id": configured["id"], "email": configured["email"]}
        print(
            "cleanup-viator-guests: SUPER_ADMIN_EMAIL is not an admin user in DB "
            f"({configured_email}), falling back to first admin user."
        )

    fallback = conn.execute(
        text(
            """
            SELECT id, email
            FROM `User`
            WHERE is_admin = 1
            ORDER BY createdAt ASC
            LIMIT 1
            """
        )
    ).mappings().first()
    if not fallback:
        raise RuntimeError(
            "cleanup-viator-guests: no admin user found. Create an admin first, then rerun."
        )
    return {"id": fallback["id"], "email": fallback["email"]}


def main() -> int:
    bootstrap()
    apply = APPLY_FLAG in sys.argv[1:]

    with db_engine() as engine:
        with engine.connect() as conn:
            target_staff = resolve_target_staff_user(conn)
            legacy_guest_users = conn.execute(
                text(
                    """
                    SELECT id, email
                    FROM `User`
                    WHERE is_admin = 0
                      AND email LIKE 'viator.%'
                      AND email LIKE '%@taxibarcelona24.guest'
                    ORDER BY createdAt ASC
                    """
                )
            ).mappings().all()

            if not legacy_guest_users:
                print("cleanup-viator-guests: no legacy Viator guest users found.")
                return 0

            legacy_ids = [row["id"] for row in legacy_guest_users]
            placeholders = ", ".join(f":id_{index}" for index in range(len(legacy_ids)))
            params = {f"id_{index}": value for index, value in enumerate(legacy_ids)}

            impacted_bookings = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM `Booking`
                    WHERE userId IN ({placeholders})
                    """
                ),
                params,
            ).scalar_one()

            print(f"cleanup-viator-guests: mode={'APPLY' if apply else 'DRY_RUN'}")
            print(
                "cleanup-viator-guests: target staff user = "
                f"{target_staff['email']} ({target_staff['id']})"
            )
            print(
                "cleanup-viator-guests: users matched = "
                f"{len(legacy_guest_users)} (pattern: {VIATOR_GUEST_EMAIL_PATTERN})"
            )
            print(f"cleanup-viator-guests: bookings to reassign = {impacted_bookings}")

            if not apply:
                print(
                    f"cleanup-viator-guests: dry-run only. Re-run with {APPLY_FLAG} to execute."
                )
                return 0

            conn.execute(
                text(
                    f"""
                    UPDATE `Booking`
                    SET userId = :target_user_id
                    WHERE userId IN ({placeholders})
                    """
                ),
                {"target_user_id": target_staff["id"], **params},
            )
            deleted = conn.execute(
                text(
                    f"""
                    DELETE FROM `User`
                    WHERE id IN ({placeholders})
                    """
                ),
                params,
            ).rowcount
            conn.commit()

    print(
        "cleanup-viator-guests: done. "
        f"bookings reassigned={impacted_bookings}, users deleted={deleted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
