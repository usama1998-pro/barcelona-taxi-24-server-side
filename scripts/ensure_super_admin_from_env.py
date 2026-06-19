"""Manual super-admin bootstrap (CLI). Run: python -m scripts.ensure_super_admin_from_env"""

from __future__ import annotations

from scripts._bootstrap import bootstrap, db_engine


def main() -> int:
    bootstrap()
    from app.lib.ensure_super_admin import (
        ensure_super_admin_from_env,
        format_ensure_super_admin_error,
        read_super_admin_bootstrap_from_env,
    )

    try:
        bootstrap_data = read_super_admin_bootstrap_from_env()
    except ValueError as error:
        print(error)
        return 1

    if bootstrap_data is None:
        print("ensure-super-admin-from-env: skipped (no SUPER_ADMIN_* env vars).")
        return 0

    print(
        "ensure-super-admin-from-env: checking DB "
        "(idempotent — only inserts if this email has no user yet)."
    )

    try:
        with db_engine() as engine:
            with engine.connect() as conn:
                result = ensure_super_admin_from_env(conn, bootstrap_data)
    except Exception as error:
        print(f"ensure-super-admin-from-env: {format_ensure_super_admin_error(error)}")
        return 1

    status = result["status"]
    if status == "exists":
        print(
            f"ensure-super-admin-from-env: super admin already exists ({bootstrap_data.email})."
        )
    elif status == "promoted":
        print(
            "ensure-super-admin-from-env: promoted existing staff user to super admin "
            f"({bootstrap_data.email})."
        )
    elif status == "created":
        print(
            "ensure-super-admin-from-env: created super admin "
            f"{result['user_id']} ({bootstrap_data.email})."
        )
    elif status == "error":
        print(f"ensure-super-admin-from-env: {result['message']}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
