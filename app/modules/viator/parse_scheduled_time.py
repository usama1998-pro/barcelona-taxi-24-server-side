from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TypedDict

from app.lib.viator_test_email import get_booking_time_zone
from app.modules.viator.booking_zoned_time import (
    calendar_parts_from_pickup_date_label,
    wall_clock_to_utc,
)

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*(am|pm)?$", re.IGNORECASE)
_TIME_IN_TEXT_RE = re.compile(r"\b(\d{1,2}:\d{2})\s*(am|pm)?\b", re.IGNORECASE)


class ViatorPickupTimeInput(TypedDict, total=False):
    departureTime: str
    disembarkationTime: str
    tourGrade: str
    tourGradeCode: str


def _parse_time_parts(time_label: str) -> dict[str, int] | None:
    match = _TIME_RE.match(time_label.strip())
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return {"hour": hour, "minute": minute}


def _extract_time_from_tour_grade_code(tour_grade_code: str | None) -> str | None:
    if not tour_grade_code:
        return None
    match = re.search(r"~(\d{1,2}:\d{2})\b", tour_grade_code)
    return match.group(1) if match else None


def _extract_time_from_tour_grade_description(tour_grade: str | None) -> str | None:
    if not tour_grade:
        return None
    match = _TIME_IN_TEXT_RE.search(tour_grade.strip())
    if not match:
        return None
    time_part = match.group(1)
    meridiem = (match.group(2) or "").strip().lower()
    return f"{time_part} {meridiem}".strip() if meridiem else time_part


def _resolve_tour_grade_pickup_time(input_data: ViatorPickupTimeInput) -> str | None:
    from_code = _extract_time_from_tour_grade_code(input_data.get("tourGradeCode"))
    if from_code:
        return from_code
    return _extract_time_from_tour_grade_description(input_data.get("tourGrade"))


def resolve_viator_pickup_time_label(input_data: ViatorPickupTimeInput) -> str | None:
    """Pickup slot from tour grade; flight departure/disembarkation are fallbacks only."""
    tour_grade_time = _resolve_tour_grade_pickup_time(input_data)
    if tour_grade_time:
        return tour_grade_time

    departure = (input_data.get("departureTime") or "").strip()
    if departure:
        return departure

    disembarkation = (input_data.get("disembarkationTime") or "").strip()
    return disembarkation or None


def parse_viator_scheduled_time_iso(
    pickup_date_label: str,
    time_input: str | ViatorPickupTimeInput | None = None,
) -> dict[str, str | bool]:
    time_zone = get_booking_time_zone()
    parts = calendar_parts_from_pickup_date_label(pickup_date_label, time_zone)

    pickup_time: str | None = None
    if isinstance(time_input, str):
        pickup_time = time_input.strip() or None
    elif time_input:
        pickup_time = resolve_viator_pickup_time_label(time_input)

    hour = 0
    minute = 0
    has_time = False
    if pickup_time:
        parsed = _parse_time_parts(pickup_time)
        if parsed:
            hour = parsed["hour"]
            minute = parsed["minute"]
            has_time = True

    scheduled = wall_clock_to_utc(
        parts["year"],
        parts["month"],
        parts["day"],
        hour,
        minute,
        time_zone,
    )
    return {"iso": scheduled.isoformat(), "hasTime": has_time}


def viator_guest_email(viator_reference: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "", viator_reference).lower()
    return f"viator.{slug}@taxibarcelona24.guest"


def parse_viator_passenger_count(travelers: str | None) -> int:
    match = re.search(r"(\d+)", travelers or "")
    if not match:
        return 1
    value = int(match.group(1))
    if value < 1:
        return 1
    return min(value, 20)


PAST_PICKUP_GRACE_MS = 60_000


def parse_scheduled_time(iso_or_date: str) -> datetime:
    value = datetime.fromisoformat(iso_or_date.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def assert_pickup_not_in_past(scheduled_time: datetime, now: datetime | None = None) -> None:
    from fastapi import HTTPException, status

    current = now or datetime.now(timezone.utc)
    if scheduled_time.timestamp() < current.timestamp() - (PAST_PICKUP_GRACE_MS / 1000):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pickup date and time must be now or in the future.",
        )
