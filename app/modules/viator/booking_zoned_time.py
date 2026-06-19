from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.lib.viator_test_email import get_booking_time_zone

_VIATOR_PICKUP_DATE_LABEL_RE = re.compile(
    r"^(?:\w+,\s*)?([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$"
)

_MONTH_NAME_TO_NUMBER = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def zoned_calendar_day_key(d: datetime, time_zone: str | None = None) -> str:
    tz = time_zone or get_booking_time_zone()
    return d.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d")


def get_zoned_date_time_parts(
    d: datetime,
    time_zone: str | None = None,
) -> dict[str, int]:
    tz = time_zone or get_booking_time_zone()
    parts = d.astimezone(ZoneInfo(tz))
    return {
        "year": parts.year,
        "month": parts.month,
        "day": parts.day,
        "hour": parts.hour,
        "minute": parts.minute,
    }


def start_of_zoned_day_with_key(
    target_key: str,
    hint_ms: float,
    time_zone: str | None = None,
) -> datetime:
    tz = time_zone or get_booking_time_zone()
    lo = hint_ms - 96 * 3600_000
    hi = hint_ms + 96 * 3600_000
    while lo < hi:
        mid = (lo + hi) // 2
        key = zoned_calendar_day_key(datetime.fromtimestamp(mid / 1000, tz=timezone.utc), tz)
        if key < target_key:
            lo = mid + 1
        else:
            hi = mid
    return datetime.fromtimestamp(lo / 1000, tz=timezone.utc)


def wall_clock_to_utc(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    time_zone: str | None = None,
) -> datetime:
    tz = time_zone or get_booking_time_zone()
    target_key = f"{year:04d}-{month:02d}-{day:02d}"
    ms = start_of_zoned_day_with_key(
        target_key,
        datetime(year, month, day, 12, tzinfo=timezone.utc).timestamp() * 1000,
        tz,
    ).timestamp() * 1000

    for _ in range(4):
        parts = get_zoned_date_time_parts(datetime.fromtimestamp(ms / 1000, tz=timezone.utc), tz)
        want_min = hour * 60 + minute
        have_min = parts["hour"] * 60 + parts["minute"]
        ms += (want_min - have_min) * 60_000

    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def calendar_parts_from_pickup_date_label(
    pickup_date_label: str,
    time_zone: str | None = None,
) -> dict[str, int]:
    trimmed = pickup_date_label.strip()
    match = _VIATOR_PICKUP_DATE_LABEL_RE.match(trimmed)
    if match:
        month = _MONTH_NAME_TO_NUMBER.get(match.group(1).lower())
        if not month:
            raise ValueError(f"Could not parse Viator travel date: {pickup_date_label}")
        day = int(match.group(2))
        year = int(match.group(3))
        if day < 1 or day > 31 or year < 2000:
            raise ValueError(f"Could not parse Viator travel date: {pickup_date_label}")
        return {"year": year, "month": month, "day": day}

    parsed = datetime.fromisoformat(trimmed.replace("Z", "+00:00"))
    parts = get_zoned_date_time_parts(parsed, time_zone)
    return {"year": parts["year"], "month": parts["month"], "day": parts["day"]}
