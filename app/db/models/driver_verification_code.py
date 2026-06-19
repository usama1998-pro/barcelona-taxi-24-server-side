from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import DatetimeMs

if TYPE_CHECKING:
    from app.db.models.driver import Driver


class DriverVerificationCode(Base):
    __tablename__ = "driver_verification_codes"

    id: Mapped[str] = mapped_column(String(191), primary_key=True)
    driver_id: Mapped[str] = mapped_column(
        "driver_id",
        String(191),
        ForeignKey("Driver.id", ondelete="CASCADE"),
        unique=True,
    )
    code: Mapped[str] = mapped_column(String(4), unique=True)
    is_active: Mapped[bool] = mapped_column("is_active", Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DatetimeMs)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DatetimeMs)

    driver: Mapped["Driver"] = relationship("Driver", back_populates="verification_code")
