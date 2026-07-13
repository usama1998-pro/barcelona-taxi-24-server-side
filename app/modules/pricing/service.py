from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.pricing_settings import PricingSettings
from app.lib.booking_pricing import (
    PRICING_SETTINGS_ROW_ID,
    defaults_public,
    get_pricing_settings,
    validate_passenger_luggage_tiers_for_save,
)
from app.modules.pricing.schemas import PricingSettingsValues


class PricingAdminService:
    def get(self, session: Session) -> dict[str, Any]:
        current = get_pricing_settings(session)
        return {
            "values": current.to_public(),
            "defaults": defaults_public(),
        }

    def update(self, session: Session, body: PricingSettingsValues) -> dict[str, Any]:
        if body.mid_max_km <= body.short_trip_max_km:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mid-range max km must be greater than short-trip max km",
            )

        try:
            tiers = validate_passenger_luggage_tiers_for_save(
                [t.model_dump() for t in body.passenger_luggage_tiers]
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        if not tiers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one valid passenger/luggage tier is required",
            )

        row = session.get(PricingSettings, PRICING_SETTINGS_ROW_ID)
        now = datetime.now(timezone.utc)
        if row is None:
            row = PricingSettings(
                id=PRICING_SETTINGS_ROW_ID,
                short_trip_max_km=body.short_trip_max_km,
                mid_max_km=body.mid_max_km,
                mid_rate_eur_per_km=body.mid_rate_eur_per_km,
                long_rate_eur_per_km=body.long_rate_eur_per_km,
                infant_carrier_fare=body.infant_carrier_fare,
                child_seat_fare=body.child_seat_fare,
                booster_fare=body.booster_fare,
                passenger_luggage_tiers=tiers,
                updated_at=now,
            )
            session.add(row)
        else:
            row.short_trip_max_km = body.short_trip_max_km
            row.mid_max_km = body.mid_max_km
            row.mid_rate_eur_per_km = body.mid_rate_eur_per_km
            row.long_rate_eur_per_km = body.long_rate_eur_per_km
            row.infant_carrier_fare = body.infant_carrier_fare
            row.child_seat_fare = body.child_seat_fare
            row.booster_fare = body.booster_fare
            row.passenger_luggage_tiers = tiers
            row.updated_at = now

        session.commit()
        return self.get(session)


pricing_admin_service = PricingAdminService()
