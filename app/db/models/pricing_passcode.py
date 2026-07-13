from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import DatetimeMs

PRICING_PASSCODE_ROW_ID = "default"


class PricingPasscode(Base):
    """Single-row passcode that gates the driver-app Prices screen / API."""

    __tablename__ = "pricing_passcode"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=PRICING_PASSCODE_ROW_ID)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DatetimeMs)
