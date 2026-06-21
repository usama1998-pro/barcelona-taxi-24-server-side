from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import HTTPException, status

PAST_PICKUP_GRACE_MS = 60_000


def get_booking_timezone() -> str:
    """IANA zone for pickup calendar days and list tabs (`BOOKING_TZ`, then `TZ`)."""
    explicit = (os.getenv("BOOKING_TZ") or os.getenv("TZ") or "").strip()
    if explicit:
        return explicit
    return "Europe/Madrid"


def parse_scheduled_time(iso_or_date: str | datetime) -> datetime:
    """Parse scheduledTime; offset/Z → UTC-aware, otherwise wall-clock naive."""
    if isinstance(iso_or_date, datetime):
        return iso_or_date
    text = iso_or_date.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    return datetime.fromisoformat(text)


def scheduled_time_for_db(iso_or_date: str | datetime) -> datetime:
    """Persist pickup as literal wall-clock naive datetime (no timezone shift)."""
    from app.modules.bookings.zoned_time import utc_aware_to_booking_db_naive

    parsed = parse_scheduled_time(iso_or_date)
    if parsed.tzinfo is None:
        return parsed
    return utc_aware_to_booking_db_naive(parsed)


def assert_pickup_not_in_past(
    scheduled_time: datetime,
    now: datetime | None = None,
) -> None:
    from app.modules.bookings.zoned_time import booking_db_naive_to_utc_aware

    reference = now or datetime.now(timezone.utc)
    if scheduled_time.tzinfo is None:
        scheduled_time = booking_db_naive_to_utc_aware(scheduled_time)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if scheduled_time.timestamp() < reference.timestamp() - (PAST_PICKUP_GRACE_MS / 1000):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pickup date and time must be now or in the future.",
        )
