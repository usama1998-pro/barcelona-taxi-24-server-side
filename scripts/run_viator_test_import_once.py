"""
Runs one synchronous test inbox import via the NestJS API (IMAP + DB).
Usage: python -m scripts.run_viator_test_import_once
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from sqlalchemy import text

from scripts._bootstrap import api_base_url, app_url_looks_local, bootstrap, db_engine


def post_inbox_check(base_url: str) -> dict:
    request = urllib.request.Request(
        f"{base_url}/viator/inbox/check",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=b"{}",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def main() -> int:
    bootstrap()
    base_url = api_base_url()
    print("Starting test inbox import (background, waiting up to 90s)...")

    try:
        enqueued = post_inbox_check(base_url)
        print("Enqueue:", enqueued)
    except urllib.error.HTTPError as error:
        print(f"POST {base_url}/viator/inbox/check failed with {error.code}")
        return 1
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", error)
        print(f"Could not reach API at {base_url}/viator/inbox/check ({reason}).")
        if app_url_looks_local():
            print(
                "APP_URL points to localhost, which is usually unreachable from CLI on "
                "shared hosting. Set APP_URL to your public API URL, or use "
                "API_BASE_URL=https://your-domain.com/api/v1"
            )
        return 1

    with db_engine() as engine:
        for _ in range(45):
            time.sleep(2)
            with engine.connect() as conn:
                latest = conn.execute(
                    text(
                        """
                        SELECT uuid, booking_reference, customer_name, createdAt
                        FROM `Booking`
                        WHERE booking_reference LIKE 'BR-%'
                        ORDER BY createdAt DESC
                        LIMIT 1
                        """
                    )
                ).mappings().first()

            if latest is None:
                continue

            created_at = latest["createdAt"]
            age_ms = (time.time() - created_at.timestamp()) * 1000
            if age_ms < 120_000:
                print("Latest booking in DB:", dict(latest))
                with engine.connect() as conn:
                    alert = conn.execute(
                        text(
                            """
                            SELECT id
                            FROM viator_alerts
                            WHERE viator_reference = :reference
                            ORDER BY received_at DESC
                            LIMIT 1
                            """
                        ),
                        {"reference": latest["booking_reference"]},
                    ).first()
                print("Matching viator_alert:", alert[0] if alert else "(none)")
                return 0

    print(
        "No new BR- booking in DB within 90s. "
        "Check logs above for IMAP timeout or import errors."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
