from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.lib.booking_pricing import (
    MIN_PASSENGER_LUGGAGE_TIERS,
    default_tier_min_price,
)


class PassengerLuggageTier(BaseModel):
    passengers: int = Field(ge=1)
    luggage: int = Field(ge=0)
    price: int = Field(ge=0)


class PricingSettingsValues(BaseModel):
    short_trip_max_km: float = Field(alias="shortTripMaxKm", gt=0)
    mid_max_km: float = Field(alias="midMaxKm", gt=0)
    mid_rate_eur_per_km: float = Field(alias="midRateEurPerKm", ge=0)
    long_rate_eur_per_km: float = Field(alias="longRateEurPerKm", ge=0)
    infant_carrier_fare: int = Field(alias="infantCarrierFare", ge=0)
    child_seat_fare: int = Field(alias="childSeatFare", ge=0)
    booster_fare: int = Field(alias="boosterFare", ge=0)
    passenger_luggage_tiers: list[PassengerLuggageTier] = Field(
        alias="passengerLuggageTiers",
        min_length=MIN_PASSENGER_LUGGAGE_TIERS,
    )

    model_config = {"populate_by_name": True}

    @field_validator("passenger_luggage_tiers")
    @classmethod
    def _validate_tiers(
        cls, value: list[PassengerLuggageTier]
    ) -> list[PassengerLuggageTier]:
        if len(value) < MIN_PASSENGER_LUGGAGE_TIERS:
            raise ValueError(
                f"At least {MIN_PASSENGER_LUGGAGE_TIERS} passenger/luggage tiers are required"
            )
        for tier in value:
            floor = default_tier_min_price(tier.passengers, tier.luggage)
            if floor is not None and tier.price < floor:
                raise ValueError(
                    f"Price for {tier.passengers} passengers / {tier.luggage} luggage "
                    f"cannot be below the default (€{floor})"
                )
        return value


class PricingUnlockBody(BaseModel):
    code: str = Field(min_length=1, max_length=16)
