from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import DatetimeMs

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.driver import Driver


class User(Base):
    __tablename__ = "User"

    id: Mapped[str] = mapped_column(String(191), primary_key=True)
    full_name: Mapped[str] = mapped_column("fullName", String(191))
    email: Mapped[str] = mapped_column(String(191), unique=True)
    phone: Mapped[str] = mapped_column(String(191), unique=True)
    password: Mapped[str] = mapped_column(String(191))
    is_admin: Mapped[bool] = mapped_column("is_admin", Boolean, default=False)
    is_super_admin: Mapped[bool] = mapped_column("is_super_admin", Boolean, default=False)
    token_version: Mapped[int] = mapped_column("token_version", Integer, default=0)
    created_at: Mapped[datetime] = mapped_column("createdAt", DatetimeMs)

    driver_profile: Mapped["Driver | None"] = relationship(
        "Driver",
        back_populates="user",
        uselist=False,
    )
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="user")
