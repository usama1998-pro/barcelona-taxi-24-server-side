from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.car import Car
    from app.db.models.driver_invoice import DriverInvoice
    from app.db.models.driver_verification_code import DriverVerificationCode
    from app.db.models.user import User


class Driver(Base):
    __tablename__ = "Driver"

    id: Mapped[str] = mapped_column(String(191), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        "user_id",
        String(191),
        ForeignKey("User.id", ondelete="SET NULL"),
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(191))
    email: Mapped[str] = mapped_column(String(191), unique=True)
    phone: Mapped[str] = mapped_column(String(191), unique=True)
    password: Mapped[str] = mapped_column(String(191))
    photo_url: Mapped[str | None] = mapped_column("photoUrl", String(191))
    rating_average: Mapped[float | None] = mapped_column("ratingAverage", Float)
    rating_count: Mapped[int] = mapped_column("ratingCount", Integer, default=0)
    is_available: Mapped[bool] = mapped_column("isAvailable", Boolean, default=True)
    is_active: Mapped[bool] = mapped_column("isActive", Boolean, default=True)
    token_version: Mapped[int] = mapped_column("token_version", Integer, default=0)

    user: Mapped["User | None"] = relationship("User", back_populates="driver_profile")
    car: Mapped["Car | None"] = relationship(
        "Car",
        back_populates="driver",
        uselist=False,
    )
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="driver")
    invoices: Mapped[list["DriverInvoice"]] = relationship(
        "DriverInvoice",
        back_populates="driver",
    )
    verification_code: Mapped["DriverVerificationCode | None"] = relationship(
        "DriverVerificationCode",
        back_populates="driver",
        uselist=False,
    )
