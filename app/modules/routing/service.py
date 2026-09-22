from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from app.modules.routing.schemas import RouteQuoteBody, get_routing_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DirectionsResult:
    distance_meters: int
    duration_seconds: int


def _parse_duration_seconds(raw: str | None) -> int:
    """Parse Routes API duration strings like ``123s`` into seconds."""
    if not raw:
        return 0
    text = raw.strip()
    if text.endswith("s"):
        text = text[:-1]
    try:
        return int(float(text))
    except ValueError:
        return 0


class GoogleDirectionsClient:
    """Driving distance/duration via Routes API (New)."""

    async def get_driving_route_between_addresses(
        self,
        from_address: str,
        to_address: str,
    ) -> DirectionsResult:
        origin = from_address.strip()
        destination = to_address.strip()
        if not origin or not destination:
            raise ValueError("Origin and destination addresses are required")

        config = get_routing_config()
        timeout = config.request_timeout_ms / 1000
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": config.google_maps_api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
        }
        body = {
            "origin": {"address": origin},
            "destination": {"address": destination},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_UNAWARE",
            "regionCode": config.region.lower(),
            "units": "METRIC",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                headers=headers,
                json=body,
            )
            data = response.json()

        if response.status_code >= 400:
            message = (
                (data.get("error") or {}).get("message")
                or data.get("message")
                or f"Google Routes failed with HTTP {response.status_code}"
            )
            raise RuntimeError(message)

        routes = data.get("routes") or []
        if not routes:
            raise RuntimeError("Google Routes returned no route")

        route = routes[0]
        distance_meters = int(route.get("distanceMeters") or 0)
        duration_seconds = _parse_duration_seconds(route.get("duration"))
        if distance_meters <= 0:
            raise RuntimeError("Google Routes returned no distance")
        return DirectionsResult(
            distance_meters=distance_meters,
            duration_seconds=duration_seconds,
        )


class GooglePlacesClient:
    """Address autocomplete via Places API (New)."""

    async def search_places(self, input_text: str) -> list[dict[str, str]]:
        query = input_text.strip()
        if not query:
            return []

        config = get_routing_config()
        timeout = config.request_timeout_ms / 1000
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": config.google_maps_api_key,
            # Field mask keeps the autocomplete payload small.
            "X-Goog-FieldMask": (
                "suggestions.placePrediction.placeId,"
                "suggestions.placePrediction.text"
            ),
        }
        body: dict = {
            "input": query,
            "includedRegionCodes": [code.lower() for code in config.country_codes],
            "regionCode": config.region.lower(),
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://places.googleapis.com/v1/places:autocomplete",
                headers=headers,
                json=body,
            )
            data = response.json()

        if response.status_code >= 400:
            message = (
                (data.get("error") or {}).get("message")
                or data.get("message")
                or f"Google Places autocomplete failed with HTTP {response.status_code}"
            )
            raise RuntimeError(message)

        results: list[dict[str, str]] = []
        for suggestion in data.get("suggestions") or []:
            prediction = suggestion.get("placePrediction") or {}
            place_id = (prediction.get("placeId") or "").strip()
            text_obj = prediction.get("text") or {}
            description = (text_obj.get("text") or "").strip()
            if not description:
                continue
            results.append({"description": description, "placeId": place_id})
        return results


class RoutingService:
    def __init__(self) -> None:
        self._places = GooglePlacesClient()
        self._directions = GoogleDirectionsClient()

    async def search_places(self, input_text: str) -> list[dict[str, str]]:
        return await self._places.search_places(input_text)

    async def get_driving_distance_km(self, from_address: str, to_address: str) -> float:
        route = await self._directions.get_driving_route_between_addresses(
            from_address,
            to_address,
        )
        return route.distance_meters / 1000

    async def get_quote(
        self,
        dto: RouteQuoteBody,
        *,
        session=None,
    ) -> dict[str, float | int]:
        from app.lib.booking_pricing import (
            DEFAULT_DISTANCE_INFANT_PRICING,
            BookingPriceInputs,
            calculate_booking_price,
            calculate_distance_surcharge,
            calculate_passenger_luggage_fare,
            get_pricing_settings,
        )

        pricing = (
            get_pricing_settings(session)
            if session is not None
            else DEFAULT_DISTANCE_INFANT_PRICING
        )

        try:
            route = await self._directions.get_driving_route_between_addresses(
                dto.from_address,
                dto.to_address,
            )
        except Exception as error:
            detail = str(error) if error else "Routing request failed"
            logger.warning("Google Directions routing failed: %s", detail)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Could not find a driving route between pickup and drop-off. "
                    "Please check the addresses and try again."
                ),
            ) from error

        distance_km = route.distance_meters / 1000
        passenger_luggage_fare = calculate_passenger_luggage_fare(
            dto.passenger_count,
            dto.luggage_count,
            pricing.passenger_luggage_tiers,
        )
        distance_surcharge_eur = (
            calculate_distance_surcharge(distance_km, pricing)
            if distance_km >= pricing.short_trip_max_km
            else 0
        )
        inputs = BookingPriceInputs(
            passenger_count=dto.passenger_count,
            luggage_count=dto.luggage_count,
            infant_carrier_count=dto.infant_carrier_count,
            child_seat_count=dto.child_seat_count,
            booster_count=dto.booster_count,
            is_return_trip=False,
            distance_km=distance_km,
        )
        one_way_price_eur = calculate_booking_price(inputs, pricing)
        return_price_eur = calculate_booking_price(
            BookingPriceInputs(
                passenger_count=inputs.passenger_count,
                luggage_count=inputs.luggage_count,
                infant_carrier_count=inputs.infant_carrier_count,
                child_seat_count=inputs.child_seat_count,
                booster_count=inputs.booster_count,
                is_return_trip=True,
                distance_km=distance_km,
            ),
            pricing,
        )
        estimated_price_eur = (
            return_price_eur if dto.is_return_trip else one_way_price_eur
        )

        return {
            "distanceKm": round(distance_km * 10) / 10,
            "distanceSurchargeEur": round(distance_surcharge_eur),
            "baseFareEur": passenger_luggage_fare,
            "oneWayPriceEur": one_way_price_eur,
            "returnPriceEur": return_price_eur,
            "estimatedPriceEur": estimated_price_eur,
            "durationMinutes": round(route.duration_seconds / 60),
        }


routing_service = RoutingService()
