from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import InvoiceAddressKind
from app.db.types import DatetimeMs

if TYPE_CHECKING:
    from app.db.models.driver import Driver


class DriverInvoice(Base):
    __tablename__ = "driver_invoices"

    id: Mapped[str] = mapped_column(String(191), primary_key=True)
    driver_id: Mapped[str] = mapped_column(
        "driver_id",
        String(191),
        ForeignKey("Driver.id", ondelete="CASCADE"),
    )
    full_name: Mapped[str] = mapped_column("full_name", String(191))
    phone_number: Mapped[str] = mapped_column("phone_number", String(191))
    booking_reference: Mapped[str] = mapped_column("booking_reference", String(191))
    pickup_date: Mapped[datetime] = mapped_column("pickup_date", DatetimeMs)
    pickup_kind: Mapped[InvoiceAddressKind] = mapped_column(
        "pickup_kind",
        SAEnum(InvoiceAddressKind, values_callable=lambda enum: [item.value for item in enum]),
    )
    pickup_address: Mapped[str | None] = mapped_column("pickup_address", String(191))
    pickup_airline: Mapped[str | None] = mapped_column("pickup_airline", String(191))
    pickup_flight_no: Mapped[str | None] = mapped_column("pickup_flight_no", String(191))
    dropoff_kind: Mapped[InvoiceAddressKind] = mapped_column(
        "dropoff_kind",
        SAEnum(InvoiceAddressKind, values_callable=lambda enum: [item.value for item in enum]),
    )
    dropoff_address: Mapped[str | None] = mapped_column("dropoff_address", String(191))
    dropoff_airline: Mapped[str | None] = mapped_column("dropoff_airline", String(191))
    dropoff_flight_no: Mapped[str | None] = mapped_column("dropoff_flight_no", String(191))
    price_amount: Mapped[Decimal] = mapped_column("price_amount", Numeric(12, 2))
    tax_rate: Mapped[Decimal] = mapped_column("tax_rate", Numeric(8, 6), default=Decimal("0.10"))
    tax_amount: Mapped[Decimal] = mapped_column("tax_amount", Numeric(12, 2))
    total_amount: Mapped[Decimal] = mapped_column("total_amount", Numeric(12, 2))
    source_booking_uuid: Mapped[str | None] = mapped_column(
        "source_booking_uuid",
        String(191),
    )
    passenger_count: Mapped[int] = mapped_column("passenger_count", Integer, default=1)
    child_seats_summary: Mapped[str | None] = mapped_column(
        "child_seats_summary",
        String(500),
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DatetimeMs)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DatetimeMs)

    driver: Mapped["Driver"] = relationship("Driver", back_populates="invoices")
