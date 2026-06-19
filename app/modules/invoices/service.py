from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.utils.ids import new_id
from app.db.enums import InvoiceAddressKind
from app.db.models.booking import Booking
from app.db.models.driver_invoice import DriverInvoice
from app.modules.auth.types import AuthenticatedUser
from app.modules.invoices.pdf_builder import build_driver_invoice_pdf
from app.modules.invoices.schemas import CreateDriverInvoiceBody, ListDriverInvoicesQuery

TAX_RATE = Decimal("0.10")


def _money_dp2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_money_response(value: Decimal) -> float:
    return float(value)


def _format_child_seats_line(infant: int, child: int, booster: int) -> str | None:
    if not infant and not child and not booster:
        return None
    parts: list[str] = []
    if infant > 0:
        parts.append(f"{infant} infant carrier{'s' if infant != 1 else ''}")
    if child > 0:
        parts.append(f"{child} child seat{'s' if child != 1 else ''}")
    if booster > 0:
        parts.append(f"{booster} booster{'s' if booster != 1 else ''}")
    return ", ".join(parts)


def _map_invoice(row: DriverInvoice) -> dict[str, Any]:
    return {
        "id": row.id,
        "driverId": row.driver_id,
        "fullName": row.full_name,
        "phoneNumber": row.phone_number,
        "bookingReference": row.booking_reference,
        "pickupDate": row.pickup_date.isoformat(),
        "pickupKind": row.pickup_kind.value,
        "pickupAddress": row.pickup_address,
        "pickupAirline": row.pickup_airline,
        "pickupFlightNo": row.pickup_flight_no,
        "dropoffKind": row.dropoff_kind.value,
        "dropoffAddress": row.dropoff_address,
        "dropoffAirline": row.dropoff_airline,
        "dropoffFlightNo": row.dropoff_flight_no,
        "priceAmount": _to_money_response(row.price_amount),
        "taxRate": _to_money_response(row.tax_rate),
        "taxAmount": _to_money_response(row.tax_amount),
        "totalAmount": _to_money_response(row.total_amount),
        "sourceBookingUuid": row.source_booking_uuid,
        "passengerCount": row.passenger_count,
        "childSeatsSummary": row.child_seats_summary,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


def _utc_day_key(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _utc_month_key(value: datetime) -> str:
    utc = value.astimezone(timezone.utc)
    return f"{utc.year:04d}-{utc.month:02d}"


def _last_7_utc_day_keys() -> list[str]:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return [(today - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(6, -1, -1)]


def _last_6_utc_month_keys_asc() -> list[str]:
    keys: list[str] = []
    cursor = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month = cursor.month - 5
    year = cursor.year
    while month <= 0:
        month += 12
        year -= 1
    cursor = cursor.replace(year=year, month=month)
    for _ in range(6):
        keys.append(_utc_month_key(cursor))
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return keys


def _utc_months_ago(months: int) -> datetime:
    now = datetime.now(timezone.utc)
    month = now.month - months
    year = now.year
    while month <= 0:
        month += 12
        year -= 1
    return now.replace(year=year, month=month, hour=0, minute=0, second=0, microsecond=0)


class DriverInvoicesService:
    @staticmethod
    def _assert_driver(user: AuthenticatedUser) -> None:
        if user.get("typ") != "driver":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only drivers can manage invoices",
            )

    @staticmethod
    def _active_booking_filters():
        return Booking.deleted_at.is_(None)

    def suggested_price_from_booking_reference(
        self,
        session: Session,
        user: AuthenticatedUser,
        booking_reference: str,
    ) -> dict[str, float | str]:
        self._assert_driver(user)
        ref = booking_reference.strip()
        booking = session.scalar(
            select(Booking).where(
                Booking.booking_reference == ref,
                Booking.driver_id == user["sub"],
                self._active_booking_filters(),
            )
        )
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No assigned booking found with that reference for your account",
            )
        return {"price": booking.price, "currency": "GBP"}

    def create(
        self,
        session: Session,
        user: AuthenticatedUser,
        dto: CreateDriverInvoiceBody,
    ) -> dict[str, Any]:
        self._assert_driver(user)

        linked_booking = session.scalar(
            select(Booking).where(
                Booking.booking_reference == dto.booking_reference.strip(),
                Booking.driver_id == user["sub"],
                self._active_booking_filters(),
            )
        )
        source_booking_uuid = linked_booking.uuid if linked_booking else None

        dto_seats = dto.child_seats_summary.strip() if dto.child_seats_summary else None
        child_seats_summary: str | None = None
        if dto_seats:
            child_seats_summary = dto_seats
        elif linked_booking:
            child_seats_summary = _format_child_seats_line(
                linked_booking.infant_carrier_count,
                linked_booking.child_seat_count,
                linked_booking.booster_count,
            )

        price_amount = _money_dp2(Decimal(str(dto.price_amount)))
        tax_amount = _money_dp2(price_amount * TAX_RATE)
        total_amount = _money_dp2(price_amount - tax_amount)

        now = datetime.now(timezone.utc)
        row = DriverInvoice(
            id=new_id(),
            driver_id=user["sub"],
            full_name=dto.full_name.strip(),
            phone_number=dto.phone_number.strip(),
            booking_reference=dto.booking_reference.strip(),
            pickup_date=dto.pickup_date,
            pickup_kind=dto.pickup_kind,
            pickup_address=(
                dto.pickup_address.strip()
                if dto.pickup_kind == InvoiceAddressKind.LOCATION and dto.pickup_address
                else None
            ),
            pickup_airline=(
                (dto.pickup_airline or "").strip() or None
                if dto.pickup_kind == InvoiceAddressKind.AIRPORT
                else None
            ),
            pickup_flight_no=(
                (dto.pickup_flight_no or "").strip() or None
                if dto.pickup_kind == InvoiceAddressKind.AIRPORT
                else None
            ),
            dropoff_kind=dto.dropoff_kind,
            dropoff_address=(
                (dto.dropoff_address or "").strip() or None
                if dto.dropoff_kind == InvoiceAddressKind.LOCATION
                else None
            ),
            dropoff_airline=(
                (dto.dropoff_airline or "").strip() or None
                if dto.dropoff_kind == InvoiceAddressKind.AIRPORT
                else None
            ),
            dropoff_flight_no=(
                (dto.dropoff_flight_no or "").strip() or None
                if dto.dropoff_kind == InvoiceAddressKind.AIRPORT
                else None
            ),
            price_amount=price_amount,
            tax_rate=TAX_RATE,
            tax_amount=tax_amount,
            total_amount=total_amount,
            source_booking_uuid=source_booking_uuid,
            passenger_count=dto.passenger_count,
            child_seats_summary=child_seats_summary,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _map_invoice(row)

    def find_all_paginated(
        self,
        session: Session,
        user: AuthenticatedUser,
        query: ListDriverInvoicesQuery,
    ) -> dict[str, Any]:
        self._assert_driver(user)
        page = query.page
        page_size = query.page_size
        skip = (page - 1) * page_size

        total = session.scalar(
            select(func.count())
            .select_from(DriverInvoice)
            .where(DriverInvoice.driver_id == user["sub"])
        ) or 0
        rows = session.scalars(
            select(DriverInvoice)
            .where(DriverInvoice.driver_id == user["sub"])
            .order_by(DriverInvoice.created_at.desc())
            .offset(skip)
            .limit(page_size)
        ).all()

        total_pages = max(1, math.ceil(total / page_size))
        return {
            "data": [_map_invoice(row) for row in rows],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": total_pages,
        }

    def find_one(
        self,
        session: Session,
        user: AuthenticatedUser,
        invoice_id: str,
    ) -> dict[str, Any]:
        self._assert_driver(user)
        row = session.scalar(
            select(DriverInvoice).where(
                DriverInvoice.id == invoice_id,
                DriverInvoice.driver_id == user["sub"],
            )
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        return _map_invoice(row)

    def build_pdf_buffer(
        self,
        session: Session,
        user: AuthenticatedUser,
        invoice_id: str,
    ) -> bytes:
        invoice = self.find_one(session, user, invoice_id)
        return build_driver_invoice_pdf(invoice)

    def get_analytics(self, session: Session, user: AuthenticatedUser) -> dict[str, Any]:
        self._assert_driver(user)
        driver_id = user["sub"]
        from6m = _utc_months_ago(6)

        totals = session.execute(
            select(
                func.coalesce(func.sum(DriverInvoice.price_amount), 0),
                func.coalesce(func.sum(DriverInvoice.tax_amount), 0),
                func.coalesce(func.sum(DriverInvoice.total_amount), 0),
                func.count(DriverInvoice.id),
            ).where(DriverInvoice.driver_id == driver_id)
        ).one()

        linked_from_booking_count = session.scalar(
            select(func.count())
            .select_from(DriverInvoice)
            .where(
                DriverInvoice.driver_id == driver_id,
                DriverInvoice.source_booking_uuid.is_not(None),
            )
        ) or 0

        rows = session.scalars(
            select(DriverInvoice).where(
                DriverInvoice.driver_id == driver_id,
                DriverInvoice.created_at >= from6m,
            )
        ).all()

        count = int(totals[3])
        subtotal = _to_money_response(Decimal(str(totals[0])))
        tax = _to_money_response(Decimal(str(totals[1])))
        invoiced = _to_money_response(Decimal(str(totals[2])))
        average_invoice_total = invoiced / count if count > 0 else 0.0

        day_keys = _last_7_utc_day_keys()
        day_totals = {key: {"total": 0.0, "count": 0} for key in day_keys}
        month_keys = _last_6_utc_month_keys_asc()
        month_totals = {
            key: {"total": 0.0, "subtotal": 0.0, "count": 0} for key in month_keys
        }

        for row in rows:
            day_key = _utc_day_key(row.created_at)
            if day_key in day_totals:
                day_totals[day_key]["total"] += _to_money_response(row.total_amount)
                day_totals[day_key]["count"] += 1
            month_key = _utc_month_key(row.created_at)
            if month_key in month_totals:
                month_totals[month_key]["total"] += _to_money_response(row.total_amount)
                month_totals[month_key]["subtotal"] += _to_money_response(row.price_amount)
                month_totals[month_key]["count"] += 1

        return {
            "count": count,
            "sums": {"subtotal": subtotal, "tax": tax, "total": invoiced},
            "averageInvoiceTotal": average_invoice_total,
            "linkedFromBookingCount": linked_from_booking_count,
            "last7Days": [
                {"date": date, "total": day_totals[date]["total"], "count": day_totals[date]["count"]}
                for date in day_keys
            ],
            "last6Months": [
                {
                    "month": month,
                    "total": month_totals[month]["total"],
                    "subtotal": month_totals[month]["subtotal"],
                    "count": month_totals[month]["count"],
                }
                for month in month_keys
            ],
        }


driver_invoices_service = DriverInvoicesService()
