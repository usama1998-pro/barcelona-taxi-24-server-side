"""Clear sign-in lockout / failed-attempt counters.

Lockouts are stored on disk (shared with the running API), so this works
without restarting the server.

Usage (from server-side, venv active):

  python -m scripts.clear_login_lockout
  python -m scripts.clear_login_lockout admin@example.com
  python -m scripts.clear_login_lockout --all
  python -m scripts.clear_login_lockout --list
"""

from __future__ import annotations

import argparse
import sys

from scripts._bootstrap import bootstrap


def main(argv: list[str] | None = None) -> int:
    bootstrap()
    from app.modules.auth.login_attempts import login_attempts, login_attempts_file

    parser = argparse.ArgumentParser(
        description="Clear password sign-in lockouts (admin / auth).",
    )
    parser.add_argument(
        "email",
        nargs="?",
        help="Email to unlock (prompts if omitted and not --all/--list)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Clear lockouts for every email",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Show tracked emails / remaining lock time",
    )
    args = parser.parse_args(argv)

    store = login_attempts_file()
    print(f"Lockout file: {store}")

    if args.list:
        rows = login_attempts.list_locked()
        if not rows:
            print("No active lockouts or failed-attempt records.")
            return 0
        for row in rows:
            if row["locked"]:
                mins = max(1, (int(row["remaining_seconds"]) + 59) // 60)
                print(
                    f"  {row['email']}: LOCKED (~{mins} min left), "
                    f"failures={row['failures']}, lockouts={row['lockouts']}"
                )
            else:
                print(
                    f"  {row['email']}: not locked, "
                    f"failures={row['failures']}, lockouts={row['lockouts']}"
                )
        return 0

    if args.all:
        count = login_attempts.clear_all()
        print(f"Cleared {count} login-attempt record(s). You can sign in again.")
        return 0

    email = (args.email or "").strip().lower()
    if not email:
        email = input("Email to unlock: ").strip().lower()
    if not email:
        print("Email is required.")
        return 1

    before = login_attempts.status(email)
    existed = login_attempts.clear(email)
    if not existed:
        print(f"No lockout record for {email} (already clear).")
        return 0

    if before.get("locked"):
        print(f"Unlocked {email} (was locked for ~{before['remaining_seconds']}s more).")
    else:
        print(f"Cleared attempt counter for {email}.")
    print("You can sign in again now (hard-refresh /my-portal if the form still shows locked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
