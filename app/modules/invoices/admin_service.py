from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.utils.ids import new_id
from app.db.enums import InvoiceAddressKind
from app.db.models.booking import Booking
from app.modules.invoices.pdf_builder import build_driver_invoice_pdf
from app.modules.invoices.schemas import CreateDriverInvoiceBody

TAX_RATE = Decimal("0.10")


def _money_dp2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class AdminInvoicesService:
    """Staff-admin invoice generation (stateless PDF; not tied to a driver)."""

    @staticmethod
    def _active_only():
        return Booking.deleted_at.is_(None)

    def suggested_price_from_reference(
        self,
        session: Session,
        booking_reference: str,
    ) -> dict[str, float | str]:
        ref = (booking_reference or "").strip()
        if not ref:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query parameter bookingReference is required",
            )
        booking = session.scalar(
            select(Booking).where(
                Booking.booking_reference == ref,
                self._active_only(),
            )
        )
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No booking found with that reference",
            )
        return {"price": booking.price, "currency": "GBP"}

    def build_pdf(self, dto: CreateDriverInvoiceBody) -> bytes:
        price_amount = _money_dp2(Decimal(str(dto.price_amount)))
        tax_amount = _money_dp2(price_amount * TAX_RATE)
        total_amount = _money_dp2(price_amount - tax_amount)

        pickup_is_location = dto.pickup_kind == InvoiceAddressKind.LOCATION
        dropoff_is_location = dto.dropoff_kind == InvoiceAddressKind.LOCATION

        invoice: dict[str, Any] = {
            "id": new_id(),
            "fullName": dto.full_name.strip(),
            "phoneNumber": dto.phone_number.strip(),
            "bookingReference": dto.booking_reference.strip(),
            "pickupDate": dto.pickup_date.isoformat(),
            "pickupKind": dto.pickup_kind.value,
            "pickupAddress": (
                (dto.pickup_address or "").strip() or None if pickup_is_location else None
            ),
            "pickupAirline": (
                None if pickup_is_location else (dto.pickup_airline or "").strip() or None
            ),
            "pickupFlightNo": (
                None if pickup_is_location else (dto.pickup_flight_no or "").strip() or None
            ),
            "dropoffKind": dto.dropoff_kind.value,
            "dropoffAddress": (
                (dto.dropoff_address or "").strip() or None if dropoff_is_location else None
            ),
            "dropoffAirline": (
                None if dropoff_is_location else (dto.dropoff_airline or "").strip() or None
            ),
            "dropoffFlightNo": (
                None if dropoff_is_location else (dto.dropoff_flight_no or "").strip() or None
            ),
            "priceAmount": float(price_amount),
            "taxAmount": float(tax_amount),
            "totalAmount": float(total_amount),
            "passengerCount": dto.passenger_count,
            "childSeatsSummary": (dto.child_seats_summary or "").strip() or None,
        }
        return build_driver_invoice_pdf(invoice)


admin_invoices_service = AdminInvoicesService()
