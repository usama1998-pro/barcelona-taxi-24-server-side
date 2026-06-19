from __future__ import annotations

import os
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.core.config import settings


@dataclass(frozen=True)
class RoutingConfig:
    google_maps_api_key: str
    country_codes: list[str]
    region: str
    request_timeout_ms: int


def get_routing_config() -> RoutingConfig:
    api_key = (settings.google_maps_api_key or "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is required")

    country_codes_raw = (os.getenv("GOOGLE_MAPS_COUNTRY_CODES") or "es").strip()
    country_codes = [
        code.strip().lower()
        for code in country_codes_raw.split(",")
        if code.strip()
    ]
    region = (os.getenv("GOOGLE_MAPS_REGION") or "es").strip() or "es"
    timeout_raw = int(os.getenv("ROUTING_TIMEOUT_MS", "30000") or "30000")
    request_timeout_ms = timeout_raw if timeout_raw > 0 else 30_000

    return RoutingConfig(
        google_maps_api_key=api_key,
        country_codes=country_codes or ["es"],
        region=region,
        request_timeout_ms=request_timeout_ms,
    )


class PlacesSearchBody(BaseModel):
    input: str = Field(min_length=1)


class RouteQuoteBody(BaseModel):
    from_address: str = Field(alias="from", min_length=1)
    to_address: str = Field(alias="to", min_length=1)
    passenger_count: int = Field(alias="passengerCount", ge=1, le=20)
    luggage_count: int = Field(alias="luggageCount", ge=0, le=50)
    infant_carrier_count: int = Field(default=0, alias="infantCarrierCount", ge=0, le=4)
    child_seat_count: int = Field(default=0, alias="childSeatCount", ge=0, le=4)
    booster_count: int = Field(default=0, alias="boosterCount", ge=0, le=4)
    is_return_trip: bool = Field(default=False, alias="isReturnTrip")

    model_config = {"populate_by_name": True}
