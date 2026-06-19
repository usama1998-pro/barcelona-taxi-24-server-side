from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.models.booking import Booking
from app.db.models.driver import Driver
from app.db.models.user import User
from app.lib.booking_reference import display_booking_reference


def _iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    utc = value.astimezone(timezone.utc)
    millis = int(utc.microsecond / 1000)
    return utc.strftime("%Y-%m-%dT%H:%M:%S") + f".{millis:03d}Z"


def _serialize_user(user: User | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "fullName": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "createdAt": _iso_datetime(user.created_at),
    }


def _serialize_driver(driver: Driver | None) -> dict[str, Any] | None:
    if driver is None:
        return None
    return {
        "id": driver.id,
        "name": driver.name,
        "email": driver.email,
        "phone": driver.phone,
        "photoUrl": driver.photo_url,
        "isAvailable": driver.is_available,
        "isActive": driver.is_active,
    }


def to_public_booking(booking: Booking) -> dict[str, Any]:
    return {
        "uuid": booking.uuid,
        "bookingReference": display_booking_reference(booking.booking_reference),
        "userId": booking.user_id,
        "driverId": booking.driver_id,
        "customerName": booking.customer_name,
        "customerEmail": booking.customer_email,
        "customerPhone": booking.customer_phone,
        "flightNumber": booking.flight_number,
        "returnTime": _iso_datetime(booking.return_time),
        "pickupLocation": booking.pickup_location,
        "dropoffLocation": booking.dropoff_location,
        "scheduledTime": _iso_datetime(booking.scheduled_time),
        "price": booking.price,
        "status": booking.status,
        "luggageCount": booking.luggage_count,
        "passengerCount": booking.passenger_count,
        "infantCarrierCount": booking.infant_carrier_count,
        "childSeatCount": booking.child_seat_count,
        "boosterCount": booking.booster_count,
        "note": booking.note,
        "createdAt": _iso_datetime(booking.created_at),
        "completedAt": _iso_datetime(booking.completed_at),
        "user": _serialize_user(booking.user),
        "driver": _serialize_driver(booking.driver),
    }


def to_public_trash_booking(booking: Booking) -> dict[str, Any]:
    payload = to_public_booking(booking)
    payload["deletedAt"] = _iso_datetime(booking.deleted_at) or _iso_datetime(
        datetime.fromtimestamp(0, tz=timezone.utc)
    )
    return payload
