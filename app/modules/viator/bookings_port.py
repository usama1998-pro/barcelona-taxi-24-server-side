from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.utils.ids import new_id
from app.db.models.booking import Booking
from app.db.models.user import User
from app.lib.booking_pricing import BookingPriceInputs, calculate_booking_price
from app.lib.booking_reference import display_booking_reference, normalize_booking_reference
from app.modules.viator.parse_scheduled_time import assert_pickup_not_in_past, parse_scheduled_time

logger = logging.getLogger(__name__)


def _extract_location_label(location: dict[str, Any] | None) -> str | None:
    if not location:
        return None
    label = location.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    address = location.get("address")
    if isinstance(address, str) and address.strip():
        return address.strip()
    return None


async def _resolve_booking_distance_km(
    pickup_location: dict[str, Any],
    dropoff_location: dict[str, Any],
) -> float | None:
    from app.modules.routing.service import routing_service

    from_address = _extract_location_label(pickup_location)
    to_address = _extract_location_label(dropoff_location)
    if not from_address or not to_address:
        return None
    try:
        return await routing_service.get_driving_distance_km(from_address, to_address)
    except Exception as error:
        logger.warning("Booking distance lookup failed: %s", error)
        return None


def find_reserved_booking_by_reference(
    session: Session,
    booking_reference: str,
) -> dict[str, Any] | None:
    ref = normalize_booking_reference(booking_reference)
    if not ref:
        return None
    row = session.execute(
        select(Booking.uuid, Booking.deleted_at)
        .where(Booking.booking_reference == ref)
        .order_by(Booking.deleted_at.asc())
        .limit(1)
    ).first()
    if not row:
        return None
    uuid, deleted_at = row
    return {"uuid": uuid, "deletedAt": deleted_at}


def is_booking_reference_reserved(
    session: Session,
    booking_reference: str,
    exclude_uuid: str | None = None,
) -> bool:
    ref = normalize_booking_reference(booking_reference)
    if not ref:
        return False
    query = select(Booking.id).where(Booking.booking_reference == ref)
    if exclude_uuid:
        query = query.where(Booking.uuid != exclude_uuid)
    return session.scalar(query.limit(1)) is not None


def find_by_booking_reference(session: Session, booking_reference: str) -> Booking | None:
    ref = normalize_booking_reference(booking_reference)
    if not ref:
        return None
    return session.scalar(
        select(Booking)
        .where(Booking.booking_reference == ref)
        .order_by(Booking.deleted_at.asc())
        .limit(1)
    )


def _resolve_viator_booking_user_id(session: Session) -> str:
    configured_staff_email = (os.getenv("SUPER_ADMIN_EMAIL") or "").strip().lower()
    if configured_staff_email:
        configured_staff = session.execute(
            select(User.id, User.is_admin).where(User.email == configured_staff_email)
        ).first()
        if configured_staff and configured_staff[1]:
            return configured_staff[0]
        logger.warning(
            "SUPER_ADMIN_EMAIL is set but not a staff user in DB: %s",
            configured_staff_email,
        )

    any_staff = session.execute(
        select(User.id, User.email)
        .where(User.is_admin.is_(True))
        .order_by(User.created_at.asc())
        .limit(1)
    ).first()
    if any_staff:
        logger.warning(
            "Viator import fallback: using staff user %s as booking owner",
            any_staff[1],
        )
        return any_staff[0]

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Cannot save Viator booking: no staff user found to attach booking owner.",
    )


async def create_from_viator(
    session: Session,
    dto: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    return await _create_from_viator_impl(session, dto)


def create_from_viator_sync(session: Session, dto: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    import asyncio

    return asyncio.run(_create_from_viator_impl(session, dto))


async def _create_from_viator_impl(
    session: Session,
    dto: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    ref = normalize_booking_reference(dto.get("bookingReference") or "")
    if ref:
        existing = find_by_booking_reference(session, ref)
        if existing:
            return _serialize_booking(existing), False

    user_id = _resolve_viator_booking_user_id(session)
    scheduled_time = parse_scheduled_time(dto["scheduledTime"])
    assert_pickup_not_in_past(scheduled_time)

    distance_km = await _resolve_booking_distance_km(
        dto["pickupLocation"],
        dto["dropoffLocation"],
    )
    computed_price = calculate_booking_price(
        BookingPriceInputs(
            passenger_count=dto["passengerCount"],
            luggage_count=dto["luggageCount"],
            infant_carrier_count=dto.get("infantCarrierCount") or 0,
            child_seat_count=dto.get("childSeatCount") or 0,
            booster_count=dto.get("boosterCount") or 0,
            is_return_trip=bool(dto.get("returnTime")),
            distance_km=distance_km,
        )
    )

    booking = Booking(
        id=new_id(),
        uuid=new_id(),
        booking_reference=ref or dto["bookingReference"],
        user_id=user_id,
        driver_id=None,
        customer_name=dto.get("customerName"),
        customer_email=dto.get("customerEmail"),
        customer_phone=dto.get("customerPhone"),
        flight_number=dto.get("flightNumber"),
        return_time=(
            parse_scheduled_time(dto["returnTime"]) if dto.get("returnTime") else None
        ),
        pickup_location=dto["pickupLocation"],
        dropoff_location=dto["dropoffLocation"],
        scheduled_time=scheduled_time.replace(tzinfo=None),
        price=float(computed_price),
        status=dto.get("status") or "PENDING",
        luggage_count=dto.get("luggageCount") or 0,
        passenger_count=dto["passengerCount"],
        infant_carrier_count=dto.get("infantCarrierCount") or 0,
        child_seat_count=dto.get("childSeatCount") or 0,
        booster_count=dto.get("boosterCount") or 0,
        note=dto.get("note"),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        completed_at=None,
        deleted_at=None,
    )

    try:
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return _serialize_booking(booking), True
    except IntegrityError:
        session.rollback()
        if ref:
            existing = find_by_booking_reference(session, ref)
            if existing:
                return _serialize_booking(existing), False
        raise


def _serialize_booking(booking: Booking) -> dict[str, Any]:
    return {
        "uuid": booking.uuid,
        "bookingReference": display_booking_reference(booking.booking_reference),
        "scheduledTime": booking.scheduled_time.isoformat(),
        "status": booking.status,
    }
