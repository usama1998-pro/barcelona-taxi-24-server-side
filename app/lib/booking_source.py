from __future__ import annotations

from typing import Any

from app.db.models.booking import Booking
from app.lib.booking_reference import display_booking_reference

GUEST_APP_EMAIL_SUFFIX = "@taxibarcelona24.guest"


def _guest_app_email(email: str | None) -> bool:
    normalized = (email or "").strip().lower()
    return normalized.startswith("guest.") and normalized.endswith(GUEST_APP_EMAIL_SUFFIX)


def _booking_customer_email(booking: Booking) -> str:
    if booking.customer_email:
        return str(booking.customer_email).strip().lower()
    if booking.user and booking.user.email:
        return booking.user.email.strip().lower()
    return ""


def _booking_customer_email_from_public(booking: dict[str, Any]) -> str:
    email = (booking.get("customerEmail") or "").strip().lower()
    if email:
        return email
    user = booking.get("user") or {}
    return ((user.get("email") or "").strip().lower()) if isinstance(user, dict) else ""


def is_viator_booking(booking: Booking) -> bool:
    email = _booking_customer_email(booking)
    if _guest_app_email(email):
        return False
    if email.startswith("viator."):
        return True
    note = (booking.note or "").strip()
    if note.startswith("[Viator"):
        return True
    ref = display_booking_reference(booking.booking_reference).strip().upper()
    return ref.startswith("BR-")


def is_app_booking(booking: Booking) -> bool:
    return _guest_app_email(_booking_customer_email(booking))


def is_website_booking(booking: Booking) -> bool:
    return not is_viator_booking(booking) and not is_app_booking(booking)


def is_viator_booking_public(booking: dict[str, Any]) -> bool:
    email = _booking_customer_email_from_public(booking)
    if _guest_app_email(email):
        return False
    if email.startswith("viator."):
        return True
    note = (booking.get("note") or "").strip()
    if note.startswith("[Viator"):
        return True
    ref = (booking.get("bookingReference") or "").strip().upper()
    return ref.startswith("BR-")


def is_app_booking_public(booking: dict[str, Any]) -> bool:
    return _guest_app_email(_booking_customer_email_from_public(booking))


def is_website_booking_public(booking: dict[str, Any]) -> bool:
    return not is_viator_booking_public(booking) and not is_app_booking_public(booking)
