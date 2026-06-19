from __future__ import annotations

import asyncio
import logging
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.common.utils.ids import new_id
from app.common.utils.password import hash_password
from app.db.models.booking import Booking
from app.db.models.driver import Driver
from app.db.models.user import User
from app.db.models.viator_alert import ViatorAlert
from app.lib.booking_pricing import BookingPriceInputs, calculate_booking_price
from app.lib.booking_reference import (
    booking_reference_search_like_pattern,
    normalize_booking_reference,
    trashed_booking_reference,
    viator_references_for_booking,
)
from app.modules.auth.types import AuthenticatedUser
from app.modules.bookings.scheduled_time import (
    assert_pickup_not_in_past,
    parse_scheduled_time,
)
from app.modules.mail.service import mail_service
from app.modules.bookings.schemas import (
    BookingTimeScope,
    CreateBookingBody,
    ListBookingsQuery,
    UpdateBookingBody,
)
from app.modules.bookings.serializers import to_public_booking, to_public_trash_booking
from app.modules.bookings.trash import (
    BOOKING_TRASH_PURGE_BATCH_SIZE,
    trash_purge_deleted_before,
)
from app.modules.bookings.zoned_time import (
    get_booking_list_scheduled_day_bounds,
    scheduled_calendar_day_bounds,
)

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = ("completed", "cancelled", "canceled")
BOOKING_LOAD_OPTIONS = (
    joinedload(Booking.user),
    joinedload(Booking.driver),
)


class BookingsService:
    def __init__(self) -> None:
        self._trash_purge_running = False
        self._trash_purge_lock = threading.Lock()

    @staticmethod
    def _extract_location_label(location: dict[str, Any]) -> str | None:
        label = location.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
        return None

    def _resolve_booking_distance_km(
        self,
        pickup_location: dict[str, Any],
        dropoff_location: dict[str, Any],
        *,
        skip: bool = False,
    ) -> float | None:
        if skip:
            return None
        from_label = self._extract_location_label(pickup_location)
        to_label = self._extract_location_label(dropoff_location)
        if not from_label or not to_label:
            return None
        from app.modules.routing.service import routing_service

        try:
            return asyncio.run(
                routing_service.get_driving_distance_km(from_label, to_label)
            )
        except Exception as error:
            logger.warning("Booking distance lookup failed: %s", error)
            return None

    @staticmethod
    def _send_booking_emails(booking: dict[str, Any]) -> dict[str, bool]:
        return asyncio.run(mail_service.send_booking_emails(booking))

    @staticmethod
    def _is_app_guest_booking_email(email: str | None) -> bool:
        normalized = (email or "").strip().lower()
        return normalized.startswith("guest.") and normalized.endswith("@taxibarcelona24.guest")

    def _is_viator_email_import(self, dto: CreateBookingBody) -> bool:
        if self._is_app_guest_booking_email(
            str(dto.customer_email) if dto.customer_email else None
        ):
            return False
        ref = (dto.booking_reference or "").strip()
        if ref.startswith("BR-"):
            return True
        email = (str(dto.customer_email) if dto.customer_email else "").strip().lower()
        if email.startswith("viator."):
            return True
        note = (dto.note or "").strip()
        return note.startswith("[Viator")

    def _should_skip_booking_emails(self, dto: CreateBookingBody) -> bool:
        return self._is_app_guest_booking_email(
            str(dto.customer_email) if dto.customer_email else None
        ) or self._is_viator_email_import(dto)

    def _is_booking_reference_reserved(
        self,
        session: Session,
        booking_reference: str,
        *,
        exclude_uuid: str | None = None,
    ) -> bool:
        ref = normalize_booking_reference(booking_reference)
        if not ref:
            return False
        stmt = select(Booking.id).where(Booking.booking_reference == ref)
        if exclude_uuid:
            stmt = stmt.where(Booking.uuid != exclude_uuid)
        return session.scalar(stmt) is not None

    def _allocate_booking_reference(
        self,
        session: Session,
        requested: str | None = None,
    ) -> str:
        trimmed = (requested or "").strip()
        if trimmed:
            normalized = normalize_booking_reference(trimmed)
            if self._is_booking_reference_reserved(session, normalized):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="That booking reference is already in use",
                )
            return normalized
        for _ in range(24):
            candidate = f"BK-{secrets.token_hex(4).upper()}"
            if not self._is_booking_reference_reserved(session, candidate):
                return candidate
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not allocate booking reference",
        )

    def _resolve_or_create_public_booking_user_id(
        self,
        session: Session,
        dto: CreateBookingBody,
    ) -> str:
        name = (dto.customer_name or "").strip()
        email = (str(dto.customer_email) if dto.customer_email else "").strip().lower()
        phone = (dto.customer_phone or "").strip()
        if not name or not email or not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "customerName, customerEmail, and customerPhone are required "
                    "for public booking creation"
                ),
            )

        by_email = session.scalar(select(User).where(User.email == email))
        if by_email:
            is_viator_guest = email.startswith("viator.") and email.endswith(
                "@taxibarcelona24.guest"
            )
            if is_viator_guest and name != by_email.full_name:
                by_email.full_name = name
                by_email.phone = phone
                session.flush()
            return by_email.id

        by_phone = session.scalar(select(User).where(User.phone == phone))
        if by_phone:
            return by_phone.id

        created = User(
            id=new_id(),
            full_name=name,
            email=email,
            phone=phone,
            password=hash_password(str(uuid.uuid4())),
            is_admin=False,
            is_super_admin=False,
            token_version=0,
            created_at=datetime.now(timezone.utc),
        )
        session.add(created)
        session.flush()
        return created.id

    def _resolve_viator_booking_user_id(self, session: Session) -> str:
        configured_email = (os.getenv("SUPER_ADMIN_EMAIL") or "").strip().lower()
        if configured_email:
            configured_staff = session.scalar(
                select(User).where(User.email == configured_email)
            )
            if configured_staff and configured_staff.is_admin:
                return configured_staff.id
            logger.warning(
                "SUPER_ADMIN_EMAIL is set but not a staff user in DB: %s",
                configured_email,
            )

        any_staff = session.scalar(
            select(User)
            .where(User.is_admin.is_(True))
            .order_by(User.created_at.asc())
            .limit(1)
        )
        if any_staff:
            logger.warning(
                "Viator import fallback: using staff user %s as booking owner",
                any_staff.email,
            )
            return any_staff.id

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cannot save Viator booking: no staff user found to attach booking owner.",
        )

    @staticmethod
    def _assert_can_view_booking(
        booking: Booking,
        requester: AuthenticatedUser,
    ) -> None:
        if requester.get("is_admin"):
            return
        if requester.get("typ") == "user":
            if booking.user_id != requester.get("sub"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You may only view your own bookings",
                )

    @staticmethod
    def _assert_can_modify_booking(
        booking: Booking,
        requester: AuthenticatedUser,
    ) -> None:
        if requester.get("is_admin"):
            return
        if requester.get("typ") == "user":
            if booking.user_id != requester.get("sub"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You may only update your own bookings",
                )

    @staticmethod
    def _assert_can_delete_booking(
        booking: Booking,
        requester: AuthenticatedUser,
    ) -> None:
        if requester.get("is_admin"):
            return
        if requester.get("typ") == "driver":
            return
        if booking.user_id != requester.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may only delete your own bookings",
            )

    def _load_booking(
        self,
        session: Session,
        uuid_value: str,
        *,
        active_only: bool = True,
    ) -> Booking | None:
        stmt = (
            select(Booking)
            .options(*BOOKING_LOAD_OPTIONS)
            .where(Booking.uuid == uuid_value)
        )
        if active_only:
            stmt = stmt.where(Booking.deleted_at.is_(None))
        return session.scalar(stmt)

    def _booking_ids_for_reference_search(
        self,
        session: Session,
        raw_query: str,
    ) -> list[str] | None:
        pattern = booking_reference_search_like_pattern(raw_query)
        if not pattern:
            return None
        rows = session.execute(
            text(
                """
                SELECT id
                FROM Booking
                WHERE deleted_at IS NULL
                  AND booking_reference COLLATE utf8mb4_unicode_ci
                    LIKE :pattern COLLATE utf8mb4_unicode_ci
                """
            ),
            {"pattern": pattern},
        ).mappings().all()
        return [row["id"] for row in rows]

    def find_reserved_booking_by_reference(
        self,
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
        if row is None:
            return None
        return {"uuid": row[0], "deletedAt": row[1]}

    def find_by_booking_reference(
        self,
        session: Session,
        booking_reference: str,
    ) -> dict[str, Any] | None:
        ref = normalize_booking_reference(booking_reference)
        if not ref:
            return None
        booking = session.scalar(
            select(Booking)
            .options(*BOOKING_LOAD_OPTIONS)
            .where(Booking.booking_reference == ref)
            .order_by(Booking.deleted_at.asc())
            .limit(1)
        )
        return to_public_booking(booking) if booking else None

    def create_from_viator(
        self,
        session: Session,
        dto: CreateBookingBody,
    ) -> dict[str, Any]:
        ref = (
            normalize_booking_reference(dto.booking_reference)
            if dto.booking_reference
            else ""
        )
        if ref:
            existing = self.find_by_booking_reference(session, ref)
            if existing:
                return {"booking": existing, "created": False}
        try:
            viator_user_id = self._resolve_viator_booking_user_id(session)
            created = self.create(
                session,
                dto.model_copy(update={"user_id": viator_user_id}),
            )
            return {"booking": created, "created": True}
        except HTTPException as err:
            if ref and err.status_code in {
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_409_CONFLICT,
            }:
                if "already in use" in str(err.detail):
                    existing = self.find_by_booking_reference(session, ref)
                    if existing:
                        return {"booking": existing, "created": False}
            raise
        except IntegrityError:
            session.rollback()
            if ref:
                existing = self.find_by_booking_reference(session, ref)
                if existing:
                    return {"booking": existing, "created": False}
            raise

    def create(
        self,
        session: Session,
        dto: CreateBookingBody,
    ) -> dict[str, Any]:
        is_viator_import = self._is_viator_email_import(dto)
        if dto.user_id:
            user_id = dto.user_id
        elif is_viator_import:
            user_id = self._resolve_viator_booking_user_id(session)
        else:
            user_id = self._resolve_or_create_public_booking_user_id(session, dto)

        infant_carrier_count = dto.infant_carrier_count or 0
        child_seat_count = dto.child_seat_count or 0
        booster_count = dto.booster_count or 0
        skip_distance_lookup = self._is_app_guest_booking_email(
            str(dto.customer_email) if dto.customer_email else None
        )
        distance_km = self._resolve_booking_distance_km(
            dto.pickup_location,
            dto.dropoff_location,
            skip=skip_distance_lookup,
        )
        computed_price = calculate_booking_price(
            BookingPriceInputs(
                passenger_count=dto.passenger_count,
                luggage_count=dto.luggage_count,
                infant_carrier_count=infant_carrier_count,
                child_seat_count=child_seat_count,
                booster_count=booster_count,
                is_return_trip=bool(dto.return_time),
                distance_km=distance_km,
            )
        )

        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        scheduled_time = parse_scheduled_time(dto.scheduled_time)
        assert_pickup_not_in_past(scheduled_time)

        driver_id: str | None = None
        if dto.driver_id:
            driver = session.get(Driver, dto.driver_id)
            if driver is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Driver {dto.driver_id} not found",
                )
            if not driver.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Driver {dto.driver_id} account is disabled",
                )
            driver_id = driver.id

        now = datetime.now(timezone.utc)
        try:
            booking_reference = self._allocate_booking_reference(
                session,
                dto.booking_reference,
            )
            booking = Booking(
                id=new_id(),
                uuid=new_id(),
                booking_reference=booking_reference,
                user_id=user_id,
                driver_id=driver_id,
                customer_name=dto.customer_name,
                customer_email=str(dto.customer_email) if dto.customer_email else None,
                customer_phone=dto.customer_phone,
                flight_number=dto.flight_number,
                return_time=parse_scheduled_time(dto.return_time) if dto.return_time else None,
                pickup_location=dto.pickup_location,
                dropoff_location=dto.dropoff_location,
                scheduled_time=scheduled_time,
                price=computed_price,
                status=dto.status,
                luggage_count=dto.luggage_count,
                passenger_count=dto.passenger_count,
                infant_carrier_count=infant_carrier_count,
                child_seat_count=child_seat_count,
                booster_count=booster_count,
                note=dto.note,
                created_at=now,
            )
            session.add(booking)
            session.commit()
        except IntegrityError as err:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That booking reference is already in use",
            ) from err

        persisted = self._load_booking(session, booking.uuid, active_only=False)
        if persisted is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Booking was not persisted",
            )

        public_booking = to_public_booking(persisted)
        notifications = {"customerEmailSent": False, "ownerEmailSent": False}
        if not self._should_skip_booking_emails(dto):
            try:
                notifications = self._send_booking_emails(public_booking)
            except Exception as err:
                logger.warning(
                    "Booking %s: confirmation emails failed",
                    public_booking["uuid"],
                    exc_info=err,
                )

        return {
            **public_booking,
            "assignmentMessage": "Booking created successfully.",
            "notifications": notifications,
        }

    def find_one_public_by_uuid(
        self,
        session: Session,
        uuid_value: str,
    ) -> dict[str, Any]:
        booking = self._load_booking(session, uuid_value)
        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking {uuid_value} not found",
            )
        return to_public_booking(booking)

    def find_all(
        self,
        session: Session,
        _requester: AuthenticatedUser,
        query: ListBookingsQuery,
    ) -> dict[str, Any]:
        conditions: list[Any] = [Booking.deleted_at.is_(None)]
        terminal_or = or_(
            Booking.status == "completed",
            Booking.status == "cancelled",
            Booking.status == "canceled",
        )
        not_terminal = ~terminal_or
        order_by: list[Any] = [Booking.created_at.desc()]

        scheduled_day_filter = None
        if query.scheduled_on:
            start, end = scheduled_calendar_day_bounds(query.scheduled_on)
            scheduled_day_filter = and_(
                Booking.scheduled_time >= start,
                Booking.scheduled_time < end,
            )

        ref_search_ids = (
            self._booking_ids_for_reference_search(session, query.booking_reference)
            if query.booking_reference
            else None
        )

        if ref_search_ids is not None:
            if ref_search_ids:
                conditions.append(Booking.id.in_(ref_search_ids))
            else:
                conditions.append(Booking.id == "__booking_ref_search_no_match__")
            if scheduled_day_filter is not None:
                conditions.append(scheduled_day_filter)
            order_by = [Booking.scheduled_time.desc()]
        elif query.time_scope == BookingTimeScope.past:
            start_of_today, _ = get_booking_list_scheduled_day_bounds()
            conditions.append(
                or_(
                    terminal_or,
                    and_(not_terminal, Booking.scheduled_time < start_of_today),
                )
            )
            if scheduled_day_filter is not None:
                conditions.append(scheduled_day_filter)
            order_by = [
                Booking.completed_at.is_(None),
                Booking.completed_at.desc(),
                Booking.scheduled_time.desc(),
                Booking.created_at.desc(),
            ]
        elif query.time_scope == BookingTimeScope.current:
            if scheduled_day_filter is not None:
                conditions.extend([not_terminal, scheduled_day_filter])
            else:
                start_of_today, start_of_tomorrow = get_booking_list_scheduled_day_bounds()
                conditions.extend(
                    [
                        not_terminal,
                        Booking.scheduled_time >= start_of_today,
                        Booking.scheduled_time < start_of_tomorrow,
                    ]
                )
            order_by = [Booking.scheduled_time.asc(), Booking.created_at.desc()]
        elif query.time_scope == BookingTimeScope.upcoming:
            if scheduled_day_filter is not None:
                conditions.extend([not_terminal, scheduled_day_filter])
            else:
                _, start_of_tomorrow = get_booking_list_scheduled_day_bounds()
                conditions.extend(
                    [not_terminal, Booking.scheduled_time >= start_of_tomorrow]
                )
            order_by = [Booking.scheduled_time.asc(), Booking.created_at.desc()]
        elif scheduled_day_filter is not None:
            conditions.append(scheduled_day_filter)
            order_by = [Booking.scheduled_time.asc()]

        where_clause = and_(*conditions)
        total = session.scalar(select(func.count()).select_from(Booking).where(where_clause)) or 0
        page = query.page
        page_size = query.page_size
        skip = (page - 1) * page_size

        rows = session.scalars(
            select(Booking)
            .options(*BOOKING_LOAD_OPTIONS)
            .where(where_clause)
            .order_by(*order_by)
            .offset(skip)
            .limit(page_size)
        ).all()

        total_pages = 0 if total == 0 else (total + page_size - 1) // page_size
        return {
            "data": [to_public_booking(row) for row in rows],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": total_pages,
        }

    def find_trash(
        self,
        session: Session,
        _requester: AuthenticatedUser,
        query: ListBookingsQuery,
    ) -> dict[str, Any]:
        where_clause = Booking.deleted_at.is_not(None)
        total = session.scalar(
            select(func.count()).select_from(Booking).where(where_clause)
        ) or 0
        page = query.page
        page_size = query.page_size
        skip = (page - 1) * page_size

        rows = session.scalars(
            select(Booking)
            .options(*BOOKING_LOAD_OPTIONS)
            .where(where_clause)
            .order_by(Booking.deleted_at.desc())
            .offset(skip)
            .limit(page_size)
        ).all()

        total_pages = 0 if total == 0 else (total + page_size - 1) // page_size
        return {
            "data": [to_public_trash_booking(row) for row in rows],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": total_pages,
        }

    def find_one(
        self,
        session: Session,
        uuid_value: str,
        requester: AuthenticatedUser,
    ) -> dict[str, Any]:
        booking = self._load_booking(session, uuid_value)
        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking {uuid_value} not found",
            )
        self._assert_can_view_booking(booking, requester)
        return to_public_booking(booking)

    def update(
        self,
        session: Session,
        uuid_value: str,
        dto: UpdateBookingBody,
        requester: AuthenticatedUser,
    ) -> dict[str, Any]:
        booking = session.scalar(
            select(Booking)
            .options(*BOOKING_LOAD_OPTIONS)
            .where(Booking.uuid == uuid_value)
        )
        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking {uuid_value} not found",
            )
        self._assert_can_modify_booking(booking, requester)

        updates: dict[str, Any] = {}
        payload = dto.model_dump(exclude_unset=True)

        if "user_id" in payload:
            if requester.get("typ") == "driver":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Drivers cannot reassign the passenger",
                )
            if (
                requester.get("typ") == "user"
                and not requester.get("is_admin")
                and payload["user_id"] != requester.get("sub")
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You may only keep bookings on your own account",
                )
            user = session.get(User, payload["user_id"])
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User {payload['user_id']} not found",
                )
            updates["user_id"] = payload["user_id"]

        if "driver_id" in payload:
            if payload["driver_id"] is None:
                if requester.get("typ") == "driver":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Drivers cannot unassign themselves here",
                    )
                updates["driver_id"] = None
            else:
                driver = session.get(Driver, payload["driver_id"])
                if driver is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Driver {payload['driver_id']} not found",
                    )
                if not driver.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Driver {payload['driver_id']} account is disabled",
                    )
                updates["driver_id"] = payload["driver_id"]

        if "pickup_location" in payload:
            updates["pickup_location"] = payload["pickup_location"]
        if "dropoff_location" in payload:
            updates["dropoff_location"] = payload["dropoff_location"]
        if "scheduled_time" in payload:
            next_scheduled = parse_scheduled_time(payload["scheduled_time"])
            assert_pickup_not_in_past(next_scheduled)
            updates["scheduled_time"] = next_scheduled

        next_passenger_count = payload.get("passenger_count", booking.passenger_count)
        next_luggage_count = payload.get("luggage_count", booking.luggage_count)
        next_infant_carrier_count = payload.get(
            "infant_carrier_count",
            booking.infant_carrier_count,
        )
        next_child_seat_count = payload.get("child_seat_count", booking.child_seat_count)
        next_booster_count = payload.get("booster_count", booking.booster_count)
        if "return_time" in payload:
            next_return_time = (
                parse_scheduled_time(payload["return_time"])
                if payload["return_time"]
                else None
            )
        else:
            next_return_time = booking.return_time

        seats_or_trip_counts_changed = any(
            key in payload
            for key in (
                "passenger_count",
                "luggage_count",
                "infant_carrier_count",
                "child_seat_count",
                "booster_count",
                "return_time",
                "pickup_location",
                "dropoff_location",
            )
        )

        if "price" in payload:
            updates["price"] = payload["price"]
        elif seats_or_trip_counts_changed:
            pickup_location = payload.get("pickup_location", booking.pickup_location)
            dropoff_location = payload.get("dropoff_location", booking.dropoff_location)
            skip_distance_lookup = self._is_app_guest_booking_email(
                booking.customer_email or (booking.user.email if booking.user else None)
            )
            distance_km = self._resolve_booking_distance_km(
                pickup_location,
                dropoff_location,
                skip=skip_distance_lookup,
            )
            updates["price"] = calculate_booking_price(
                BookingPriceInputs(
                    passenger_count=next_passenger_count,
                    luggage_count=next_luggage_count,
                    infant_carrier_count=next_infant_carrier_count,
                    child_seat_count=next_child_seat_count,
                    booster_count=next_booster_count,
                    is_return_trip=bool(next_return_time),
                    distance_km=distance_km,
                )
            )

        became_completed = False
        if "status" in payload:
            next_raw = str(payload["status"]).strip()
            next_lower = next_raw.lower()
            cur_lower = booking.status.lower()
            already_terminal = cur_lower in TERMINAL_STATUSES
            if already_terminal:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change status of a closed booking",
                )
            if requester.get("typ") == "driver":
                if next_lower == "completed":
                    if cur_lower != "in_progress":
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Start the ride before marking it complete",
                        )
                    updates["status"] = "completed"
                    updates["completed_at"] = datetime.now(timezone.utc)
                    became_completed = True
                elif next_lower == "in_progress":
                    updates["status"] = "in_progress"
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Drivers may only start a ride (in progress) or mark it complete",
                    )
            else:
                updates["status"] = next_raw
                if next_lower == "completed":
                    updates["completed_at"] = datetime.now(timezone.utc)
                    became_completed = True
                elif next_lower in ("cancelled", "canceled"):
                    updates["completed_at"] = None

        for field, key in (
            ("luggage_count", "luggage_count"),
            ("passenger_count", "passenger_count"),
            ("infant_carrier_count", "infant_carrier_count"),
            ("child_seat_count", "child_seat_count"),
            ("booster_count", "booster_count"),
            ("note", "note"),
            ("customer_name", "customer_name"),
            ("customer_email", "customer_email"),
            ("customer_phone", "customer_phone"),
            ("flight_number", "flight_number"),
        ):
            if key in payload:
                updates[field] = payload[key]

        if "return_time" in payload:
            updates["return_time"] = next_return_time

        if "booking_reference" in payload:
            if requester.get("typ") == "driver":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Drivers cannot change booking reference",
                )
            ref = (payload["booking_reference"] or "").strip()
            if not ref:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="bookingReference cannot be empty",
                )
            if self._is_booking_reference_reserved(session, ref, exclude_uuid=uuid_value):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="That booking reference is already in use",
                )
            updates["booking_reference"] = normalize_booking_reference(ref)

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )

        original_driver_id = booking.driver_id
        for field, value in updates.items():
            setattr(booking, field, value)
        session.flush()

        if became_completed and original_driver_id:
            active_other = session.scalar(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.driver_id == original_driver_id,
                    Booking.uuid != uuid_value,
                    Booking.deleted_at.is_(None),
                    ~or_(
                        Booking.status == "completed",
                        Booking.status == "cancelled",
                        Booking.status == "canceled",
                    ),
                )
            ) or 0
            if active_other == 0:
                driver = session.get(Driver, original_driver_id)
                if driver is not None:
                    driver.is_available = True

        session.commit()
        session.refresh(booking)
        return to_public_booking(booking)

    def complete_reservation(
        self,
        session: Session,
        uuid_value: str,
        requester: AuthenticatedUser,
    ) -> dict[str, Any]:
        booking = self._load_booking(session, uuid_value)
        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking {uuid_value} not found",
            )
        self._assert_can_modify_booking(booking, requester)

        cur_lower = booking.status.lower()
        if cur_lower in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot complete a closed booking",
            )

        booking.status = "completed"
        booking.completed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(booking)
        return to_public_booking(booking)

    def remove(
        self,
        session: Session,
        uuid_value: str,
        requester: AuthenticatedUser,
    ) -> dict[str, Any]:
        booking = self._load_booking(session, uuid_value)
        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking {uuid_value} not found",
            )
        self._assert_can_delete_booking(booking, requester)

        driver_id = booking.driver_id
        original_reference = booking.booking_reference
        trashed_reference = trashed_booking_reference(original_reference, uuid_value)
        viator_refs = viator_references_for_booking(original_reference)
        now = datetime.now(timezone.utc)

        session.execute(
            update(ViatorAlert)
            .where(
                or_(
                    ViatorAlert.booking_uuid == uuid_value,
                    ViatorAlert.viator_reference.in_(viator_refs),
                )
            )
            .values(dismissed_at=now)
        )
        booking.deleted_at = now
        booking.booking_reference = trashed_reference

        if driver_id:
            remaining = session.scalar(
                select(func.count())
                .select_from(Booking)
                .where(Booking.driver_id == driver_id, Booking.deleted_at.is_(None))
            ) or 0
            if remaining == 0:
                driver = session.get(Driver, driver_id)
                if driver is not None:
                    driver.is_available = True

        session.commit()
        return {
            "success": True,
            "message": "Booking moved to trash.",
            "uuid": uuid_value,
        }

    def enqueue_purge_trash_batch(self) -> dict[str, Any]:
        with self._trash_purge_lock:
            if self._trash_purge_running:
                return {
                    "accepted": False,
                    "status": "already_running",
                    "batchSize": BOOKING_TRASH_PURGE_BATCH_SIZE,
                    "message": (
                        "A trash purge is already running. Call again later if more "
                        "batches are needed."
                    ),
                }
            self._trash_purge_running = True

        thread = threading.Thread(
            target=self._run_purge_trash_batch_in_background,
            daemon=True,
        )
        thread.start()

        return {
            "accepted": True,
            "status": "started",
            "batchSize": BOOKING_TRASH_PURGE_BATCH_SIZE,
            "message": (
                f"Trash purge started in the background (up to "
                f"{BOOKING_TRASH_PURGE_BATCH_SIZE} bookings per batch)."
            ),
        }

    def _run_purge_trash_batch_in_background(self) -> None:
        from app.db.session import _session_factory

        session = _session_factory()()
        try:
            self.purge_trash_batch(session)
        except Exception as err:
            logger.warning("Trash purge batch failed: %s", err)
        finally:
            session.close()
            with self._trash_purge_lock:
                self._trash_purge_running = False

    def _trash_purge_where(self) -> list[Any]:
        deleted_before = trash_purge_deleted_before()
        if deleted_before is not None:
            return [Booking.deleted_at.is_not(None), Booking.deleted_at < deleted_before]
        return [Booking.deleted_at.is_not(None)]

    def _hard_delete_booking(
        self,
        session: Session,
        booking: Booking,
    ) -> None:
        viator_refs = viator_references_for_booking(booking.booking_reference)
        session.execute(
            delete(ViatorAlert).where(
                or_(
                    ViatorAlert.booking_uuid == booking.uuid,
                    ViatorAlert.viator_reference.in_(viator_refs),
                )
            )
        )
        driver_id = booking.driver_id
        session.delete(booking)
        session.flush()
        if driver_id:
            remaining = session.scalar(
                select(func.count())
                .select_from(Booking)
                .where(Booking.driver_id == driver_id, Booking.deleted_at.is_(None))
            ) or 0
            if remaining == 0:
                driver = session.get(Driver, driver_id)
                if driver is not None:
                    driver.is_available = True

    def purge_trash_batch(self, session: Session) -> dict[str, Any]:
        where_conditions = self._trash_purge_where()
        candidates = session.scalars(
            select(Booking)
            .where(*where_conditions)
            .order_by(Booking.deleted_at.asc())
            .limit(BOOKING_TRASH_PURGE_BATCH_SIZE)
        ).all()

        if not candidates:
            remaining_in_trash = session.scalar(
                select(func.count()).select_from(Booking).where(*where_conditions)
            ) or 0
            return {
                "purged": 0,
                "batchSize": BOOKING_TRASH_PURGE_BATCH_SIZE,
                "uuids": [],
                "remainingInTrash": remaining_in_trash,
            }

        for row in candidates:
            self._hard_delete_booking(session, row)
        session.commit()

        remaining_in_trash = session.scalar(
            select(func.count()).select_from(Booking).where(*where_conditions)
        ) or 0
        logger.info(
            "Trash purge batch: removed %s booking(s); %s still in trash",
            len(candidates),
            remaining_in_trash,
        )
        return {
            "purged": len(candidates),
            "batchSize": BOOKING_TRASH_PURGE_BATCH_SIZE,
            "uuids": [row.uuid for row in candidates],
            "remainingInTrash": remaining_in_trash,
        }

    def clear_trash(self, session: Session) -> dict[str, Any]:
        where_conditions = self._trash_purge_where()
        candidates = session.scalars(
            select(Booking)
            .where(*where_conditions)
            .order_by(Booking.deleted_at.asc())
        ).all()

        if not candidates:
            return {"purged": 0, "uuids": [], "remainingInTrash": 0}

        uuids: list[str] = []
        for index in range(0, len(candidates), BOOKING_TRASH_PURGE_BATCH_SIZE):
            chunk = candidates[index : index + BOOKING_TRASH_PURGE_BATCH_SIZE]
            for row in chunk:
                self._hard_delete_booking(session, row)
                uuids.append(row.uuid)
            session.commit()

        remaining_in_trash = session.scalar(
            select(func.count()).select_from(Booking).where(*where_conditions)
        ) or 0
        logger.info(
            "Trash cleared: permanently removed %s booking(s); %s still in trash",
            len(uuids),
            remaining_in_trash,
        )
        return {
            "purged": len(uuids),
            "uuids": uuids,
            "remainingInTrash": remaining_in_trash,
        }


bookings_service = BookingsService()
