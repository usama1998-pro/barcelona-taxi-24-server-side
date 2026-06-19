from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import HTTPException, status

PAST_PICKUP_GRACE_MS = 60_000


def get_booking_timezone() -> str:
    return (os.getenv("TZ") or "").strip() or "Europe/Madrid"


def parse_scheduled_time(iso_or_date: str | datetime) -> datetime:
    if isinstance(iso_or_date, datetime):
        parsed = iso_or_date
    else:
        text = iso_or_date.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def assert_pickup_not_in_past(
    scheduled_time: datetime,
    now: datetime | None = None,
) -> None:
    reference = now or datetime.now(timezone.utc)
    if scheduled_time.tzinfo is None:
        scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if scheduled_time.timestamp() < reference.timestamp() - (PAST_PICKUP_GRACE_MS / 1000):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pickup date and time must be now or in the future.",
        )
