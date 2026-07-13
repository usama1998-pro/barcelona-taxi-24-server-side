from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import DatetimeMs


class PricingSettings(Base):
    """Single-row admin-editable pricing knobs (tiers, distance, seat fees)."""

    __tablename__ = "pricing_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")
    short_trip_max_km: Mapped[float] = mapped_column(Float, nullable=False)
    mid_max_km: Mapped[float] = mapped_column(Float, nullable=False)
    mid_rate_eur_per_km: Mapped[float] = mapped_column(Float, nullable=False)
    long_rate_eur_per_km: Mapped[float] = mapped_column(Float, nullable=False)
    infant_carrier_fare: Mapped[int] = mapped_column(Integer, nullable=False)
    child_seat_fare: Mapped[int] = mapped_column(Integer, nullable=False)
    booster_fare: Mapped[int] = mapped_column(Integer, nullable=False)
    passenger_luggage_tiers: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column("updated_at", DatetimeMs)
