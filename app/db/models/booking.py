from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import DatetimeMs

if TYPE_CHECKING:
    from app.db.models.driver import Driver
    from app.db.models.user import User


class Booking(Base):
    __tablename__ = "Booking"

    id: Mapped[str] = mapped_column(String(191), primary_key=True)
    uuid: Mapped[str] = mapped_column(String(191), unique=True)
    booking_reference: Mapped[str] = mapped_column("booking_reference", String(191), unique=True)
    user_id: Mapped[str] = mapped_column(
        "userId",
        String(191),
        ForeignKey("User.id", ondelete="CASCADE"),
    )
    driver_id: Mapped[str | None] = mapped_column(
        "driverId",
        String(191),
        ForeignKey("Driver.id", ondelete="SET NULL"),
    )
    customer_name: Mapped[str | None] = mapped_column("customer_name", String(191))
    customer_email: Mapped[str | None] = mapped_column("customer_email", String(191))
    customer_phone: Mapped[str | None] = mapped_column("customer_phone", String(191))
    flight_number: Mapped[str | None] = mapped_column("flight_number", String(191))
    return_time: Mapped[datetime | None] = mapped_column("return_time", DatetimeMs)
    pickup_location: Mapped[dict[str, Any]] = mapped_column("pickupLocation", JSON)
    dropoff_location: Mapped[dict[str, Any]] = mapped_column("dropoffLocation", JSON)
    scheduled_time: Mapped[datetime] = mapped_column("scheduledTime", DatetimeMs)
    price: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(191))
    luggage_count: Mapped[int] = mapped_column("luggageCount", Integer)
    passenger_count: Mapped[int] = mapped_column("passengerCount", Integer)
    infant_carrier_count: Mapped[int] = mapped_column("infantCarrierCount", Integer, default=0)
    child_seat_count: Mapped[int] = mapped_column("childSeatCount", Integer, default=0)
    booster_count: Mapped[int] = mapped_column("boosterCount", Integer, default=0)
    note: Mapped[str | None] = mapped_column(String(191))
    created_at: Mapped[datetime] = mapped_column("createdAt", DatetimeMs)
    completed_at: Mapped[datetime | None] = mapped_column("completed_at", DatetimeMs)
    deleted_at: Mapped[datetime | None] = mapped_column("deleted_at", DatetimeMs)

    user: Mapped["User"] = relationship("User", back_populates="bookings")
    driver: Mapped["Driver | None"] = relationship("Driver", back_populates="bookings")
