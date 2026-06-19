from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

BOOKING_TRASH_PURGE_BATCH_SIZE = 30


def booking_trash_retention_days() -> int:
    raw = (os.getenv("BOOKING_TRASH_RETENTION_DAYS") or "").strip()
    if not raw:
        return 0
    try:
        value = int(raw, 10)
    except ValueError:
        return 0
    return value if value >= 0 else 0


def trash_purge_deleted_before() -> datetime | None:
    retention_days = booking_trash_retention_days()
    if retention_days <= 0:
        return None
    return datetime.now(timezone.utc) - timedelta(days=retention_days)
