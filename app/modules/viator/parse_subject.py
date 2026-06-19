from __future__ import annotations

import re

from app.lib.viator_test_email import (
    is_viator_test_booking_subject,
    parse_viator_test_booking_subject,
)

_VIATOR_NEW_BOOKING_SUBJECT = re.compile(
    r"^(?:Re:\s*|Fwd:\s*|Fw:\s*)*New Booking for (.+?) \(#(BR-\d+)\)\s*$",
    re.IGNORECASE,
)


def normalize_viator_email_subject(subject: str) -> str:
    return re.sub(r"\s+", " ", subject).strip()


def parse_viator_new_booking_subject(subject: str) -> dict[str, str] | None:
    match = _VIATOR_NEW_BOOKING_SUBJECT.match(normalize_viator_email_subject(subject))
    if not match:
        return None
    return {
        "pickupDateLabel": match.group(1).strip(),
        "viatorReference": match.group(2).strip().upper(),
    }


def is_viator_new_booking_subject(subject: str) -> bool:
    return parse_viator_new_booking_subject(subject) is not None


__all__ = [
    "is_viator_new_booking_subject",
    "is_viator_test_booking_subject",
    "normalize_viator_email_subject",
    "parse_viator_new_booking_subject",
    "parse_viator_test_booking_subject",
]
