from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.modules.bookings.scheduled_time import get_booking_timezone


def booking_zoneinfo(time_zone: str | None = None) -> ZoneInfo:
    return ZoneInfo(time_zone or get_booking_timezone())


def as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_aware_to_booking_db_naive(
    value: datetime,
    time_zone: str | None = None,
) -> datetime:
    """UTC instant → wall-clock naive datetime in the booking timezone (DB format)."""
    tz = booking_zoneinfo(time_zone)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz).replace(tzinfo=None)


def booking_db_naive_to_utc_aware(
    value: datetime,
    time_zone: str | None = None,
) -> datetime:
    """Wall-clock naive datetime from DB → UTC-aware instant."""
    tz = booking_zoneinfo(time_zone)
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.replace(tzinfo=tz).astimezone(timezone.utc)


def zoned_calendar_day_key(
    value: datetime,
    time_zone: str | None = None,
) -> str:
    tz_name = time_zone or get_booking_timezone()
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d")
    local = value.astimezone(booking_zoneinfo(tz_name))
    return local.strftime("%Y-%m-%d")


def start_of_zoned_day_with_key(
    target_key: str,
    hint_ms: float,
    time_zone: str | None = None,
) -> datetime:
    tz_name = time_zone or get_booking_timezone()
    lo = hint_ms - 96 * 3_600_000
    hi = hint_ms + 96 * 3_600_000
    while lo < hi:
        mid = (lo + hi) // 2
        key = zoned_calendar_day_key(
            datetime.fromtimestamp(mid / 1000, tz=timezone.utc),
            tz_name,
        )
        if key < target_key:
            lo = mid + 1
        else:
            hi = mid
    return datetime.fromtimestamp(lo / 1000, tz=timezone.utc)


def scheduled_calendar_day_bounds(
    day_key: str,
    time_zone: str | None = None,
) -> tuple[datetime, datetime]:
    tz_name = time_zone or get_booking_timezone()
    hint = datetime.fromisoformat(f"{day_key}T12:00:00+00:00").timestamp() * 1000
    start = start_of_zoned_day_with_key(day_key, hint, tz_name)
    probe = start.timestamp() * 1000 + 6 * 3_600_000
    while (
        zoned_calendar_day_key(
            datetime.fromtimestamp(probe / 1000, tz=timezone.utc),
            tz_name,
        )
        == day_key
    ):
        probe += 3_600_000
    next_key = zoned_calendar_day_key(
        datetime.fromtimestamp(probe / 1000, tz=timezone.utc),
        tz_name,
    )
    end = start_of_zoned_day_with_key(next_key, probe, tz_name)
    return start, end


def get_booking_list_scheduled_day_bounds(
    time_zone: str | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    tz_name = time_zone or get_booking_timezone()
    reference = now or datetime.now(timezone.utc)
    today_key = zoned_calendar_day_key(reference, tz_name)
    start_of_today = start_of_zoned_day_with_key(
        today_key,
        reference.timestamp() * 1000,
        tz_name,
    )
    probe = start_of_today.timestamp() * 1000 + 6 * 3_600_000
    while (
        zoned_calendar_day_key(
            datetime.fromtimestamp(probe / 1000, tz=timezone.utc),
            tz_name,
        )
        == today_key
    ):
        probe += 3_600_000
    tomorrow_key = zoned_calendar_day_key(
        datetime.fromtimestamp(probe / 1000, tz=timezone.utc),
        tz_name,
    )
    start_of_tomorrow = start_of_zoned_day_with_key(tomorrow_key, probe, tz_name)
    return start_of_today, start_of_tomorrow


def get_booking_list_scheduled_day_bounds_db_naive(
    time_zone: str | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Today's [start, tomorrow) as wall-clock naive values stored in `scheduledTime`."""
    start_of_today, start_of_tomorrow = get_booking_list_scheduled_day_bounds(
        time_zone,
        now,
    )
    return (
        utc_aware_to_booking_db_naive(start_of_today, time_zone),
        utc_aware_to_booking_db_naive(start_of_tomorrow, time_zone),
    )
