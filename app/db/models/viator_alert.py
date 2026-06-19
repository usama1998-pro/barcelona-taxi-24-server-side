from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import DatetimeMs


class ViatorAlert(Base):
    __tablename__ = "viator_alerts"
    __table_args__ = (
        Index("viator_alerts_dismissed_at_received_at_idx", "dismissed_at", "received_at"),
    )

    id: Mapped[str] = mapped_column(String(191), primary_key=True)
    viator_reference: Mapped[str] = mapped_column(
        "viator_reference",
        String(191),
        unique=True,
    )
    subject: Mapped[str] = mapped_column(String(500))
    pickup_date_label: Mapped[str] = mapped_column("pickup_date_label", String(200))
    received_at: Mapped[datetime] = mapped_column("received_at", DatetimeMs)
    booking_uuid: Mapped[str | None] = mapped_column("booking_uuid", String(191))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    dismissed_at: Mapped[datetime | None] = mapped_column("dismissed_at", DatetimeMs)
    created_at: Mapped[datetime] = mapped_column("created_at", DatetimeMs)
