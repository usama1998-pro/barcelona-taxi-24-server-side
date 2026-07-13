from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy.orm import Session

PASSENGER_LUGGAGE_RATE_TIERS: list[dict[str, int]] = [
    {"passengers": 1, "luggage": 1, "price": 52},
    {"passengers": 2, "luggage": 2, "price": 52},
    {"passengers": 3, "luggage": 3, "price": 57},
    {"passengers": 4, "luggage": 4, "price": 62},
    {"passengers": 5, "luggage": 5, "price": 72},
    {"passengers": 6, "luggage": 6, "price": 77},
    {"passengers": 7, "luggage": 7, "price": 84},
    {"passengers": 8, "luggage": 8, "price": 110},
    {"passengers": 8, "luggage": 12, "price": 127},
    {"passengers": 8, "luggage": 16, "price": 153},
]

MIN_PASSENGER_LUGGAGE_TIERS = len(PASSENGER_LUGGAGE_RATE_TIERS)

DEFAULT_TIER_PRICE_BY_KEY: dict[tuple[int, int], int] = {
    (int(t["passengers"]), int(t["luggage"])): int(t["price"])
    for t in PASSENGER_LUGGAGE_RATE_TIERS
}

# Kept as defaults for DB-backed distance / seat settings.
DISTANCE_SHORT_TRIP_MAX_KM = 17
DISTANCE_MID_RATE_EUR_PER_KM = 4
DISTANCE_MID_MAX_KM = 32
DISTANCE_LONG_RATE_EUR_PER_KM = 2
INFANT_CARRIER_FARE = 7
CHILD_SEAT_FARE = 7
BOOSTER_FARE = 7

PRICING_SETTINGS_ROW_ID = "default"


def normalize_passenger_luggage_tiers(
    tiers: Sequence[dict[str, Any]] | None,
) -> list[dict[str, int]]:
    """Validate and normalize tier rows; fall back to defaults if empty/invalid."""
    if not tiers:
        return [dict(t) for t in PASSENGER_LUGGAGE_RATE_TIERS]

    normalized: list[dict[str, int]] = []
    for raw in tiers:
        try:
            passengers = int(raw["passengers"])
            luggage = int(raw["luggage"])
            price = int(raw["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if passengers < 1 or luggage < 0 or price < 0:
            continue
        normalized.append(
            {"passengers": passengers, "luggage": luggage, "price": price}
        )

    if not normalized:
        return [dict(t) for t in PASSENGER_LUGGAGE_RATE_TIERS]

    normalized.sort(key=lambda t: (t["passengers"], t["luggage"], t["price"]))
    return normalized


def default_tier_min_price(passengers: int, luggage: int) -> int | None:
    """Return the default floor price for a passengers/luggage pair, if any."""
    return DEFAULT_TIER_PRICE_BY_KEY.get((int(passengers), int(luggage)))


def validate_passenger_luggage_tiers_for_save(
    tiers: Sequence[dict[str, int]],
) -> list[dict[str, int]]:
    """Normalize and enforce save rules: min tier count + no price below default."""
    normalized = normalize_passenger_luggage_tiers(tiers)
    if len(normalized) < MIN_PASSENGER_LUGGAGE_TIERS:
        raise ValueError(
            f"At least {MIN_PASSENGER_LUGGAGE_TIERS} passenger/luggage tiers are required"
        )

    for tier in normalized:
        floor = default_tier_min_price(tier["passengers"], tier["luggage"])
        if floor is not None and tier["price"] < floor:
            raise ValueError(
                f"Price for {tier['passengers']} passengers / {tier['luggage']} luggage "
                f"cannot be below the default (€{floor})"
            )
    return normalized


def max_tier_price(tiers: Sequence[dict[str, int]]) -> int:
    if not tiers:
        return PASSENGER_LUGGAGE_RATE_TIERS[-1]["price"]
    return max(int(t["price"]) for t in tiers)


@dataclass(frozen=True)
class DistanceInfantPricingSettings:
    short_trip_max_km: float
    mid_max_km: float
    mid_rate_eur_per_km: float
    long_rate_eur_per_km: float
    infant_carrier_fare: int
    child_seat_fare: int
    booster_fare: int
    passenger_luggage_tiers: tuple[dict[str, int], ...]

    def to_public(self) -> dict[str, float | int | list[dict[str, int]]]:
        return {
            "shortTripMaxKm": self.short_trip_max_km,
            "midMaxKm": self.mid_max_km,
            "midRateEurPerKm": self.mid_rate_eur_per_km,
            "longRateEurPerKm": self.long_rate_eur_per_km,
            "infantCarrierFare": self.infant_carrier_fare,
            "childSeatFare": self.child_seat_fare,
            "boosterFare": self.booster_fare,
            "passengerLuggageTiers": [dict(t) for t in self.passenger_luggage_tiers],
        }


DEFAULT_DISTANCE_INFANT_PRICING = DistanceInfantPricingSettings(
    short_trip_max_km=float(DISTANCE_SHORT_TRIP_MAX_KM),
    mid_max_km=float(DISTANCE_MID_MAX_KM),
    mid_rate_eur_per_km=float(DISTANCE_MID_RATE_EUR_PER_KM),
    long_rate_eur_per_km=float(DISTANCE_LONG_RATE_EUR_PER_KM),
    infant_carrier_fare=int(INFANT_CARRIER_FARE),
    child_seat_fare=int(CHILD_SEAT_FARE),
    booster_fare=int(BOOSTER_FARE),
    passenger_luggage_tiers=tuple(
        dict(t) for t in PASSENGER_LUGGAGE_RATE_TIERS
    ),
)


@dataclass(frozen=True)
class BookingPriceInputs:
    passenger_count: int
    luggage_count: int
    infant_carrier_count: int
    child_seat_count: int
    booster_count: int
    is_return_trip: bool = False
    distance_km: float | None = None


def calculate_passenger_luggage_fare(
    passenger_count: int,
    luggage_count: int,
    tiers: Sequence[dict[str, int]] | None = None,
) -> int:
    rate_tiers = normalize_passenger_luggage_tiers(tiers)
    passengers = max(1, int(passenger_count))
    luggage = max(0, int(luggage_count))
    effective_luggage = luggage if luggage > 0 else 1

    fitting = [
        tier
        for tier in rate_tiers
        if tier["passengers"] >= passengers and tier["luggage"] >= effective_luggage
    ]
    if not fitting:
        return max_tier_price(rate_tiers)
    return min(tier["price"] for tier in fitting)


def calculate_distance_surcharge(
    distance_km: float,
    settings: DistanceInfantPricingSettings | None = None,
) -> float:
    cfg = settings or DEFAULT_DISTANCE_INFANT_PRICING
    km = max(0.0, distance_km)
    if km < cfg.short_trip_max_km:
        return 0.0
    if km <= cfg.mid_max_km:
        return km * cfg.mid_rate_eur_per_km
    return km * cfg.long_rate_eur_per_km


def calculate_booking_price(
    input_data: BookingPriceInputs,
    settings: DistanceInfantPricingSettings | None = None,
) -> int:
    cfg = settings or DEFAULT_DISTANCE_INFANT_PRICING
    infant_extra = max(0, input_data.infant_carrier_count) * cfg.infant_carrier_fare
    child_extra = max(0, input_data.child_seat_count) * cfg.child_seat_fare
    booster_extra = max(0, input_data.booster_count) * cfg.booster_fare
    seat_extras = infant_extra + child_extra + booster_extra

    tier_fare = calculate_passenger_luggage_fare(
        input_data.passenger_count,
        input_data.luggage_count,
        cfg.passenger_luggage_tiers,
    )
    distance_fare = 0.0
    if (
        input_data.distance_km is not None
        and input_data.distance_km >= cfg.short_trip_max_km
    ):
        distance_fare = calculate_distance_surcharge(input_data.distance_km, cfg)

    one_way_total = tier_fare + distance_fare + seat_extras
    total = one_way_total * 2 if input_data.is_return_trip else one_way_total
    return round(total)


def get_pricing_settings(session: Session) -> DistanceInfantPricingSettings:
    """Load DB settings merged over hardcoded defaults (field-level fallback)."""
    from app.db.models.pricing_settings import PricingSettings

    row = session.get(PricingSettings, PRICING_SETTINGS_ROW_ID)
    if row is None:
        return DEFAULT_DISTANCE_INFANT_PRICING

    def _float(value: Any, fallback: float) -> float:
        try:
            if value is None:
                return fallback
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _int(value: Any, fallback: int) -> int:
        try:
            if value is None:
                return fallback
            return int(value)
        except (TypeError, ValueError):
            return fallback

    defaults = DEFAULT_DISTANCE_INFANT_PRICING
    raw_tiers = getattr(row, "passenger_luggage_tiers", None)
    tiers = normalize_passenger_luggage_tiers(
        raw_tiers if isinstance(raw_tiers, list) else None
    )
    return DistanceInfantPricingSettings(
        short_trip_max_km=_float(row.short_trip_max_km, defaults.short_trip_max_km),
        mid_max_km=_float(row.mid_max_km, defaults.mid_max_km),
        mid_rate_eur_per_km=_float(row.mid_rate_eur_per_km, defaults.mid_rate_eur_per_km),
        long_rate_eur_per_km=_float(
            row.long_rate_eur_per_km, defaults.long_rate_eur_per_km
        ),
        infant_carrier_fare=_int(row.infant_carrier_fare, defaults.infant_carrier_fare),
        child_seat_fare=_int(
            getattr(row, "child_seat_fare", None), defaults.child_seat_fare
        ),
        booster_fare=_int(getattr(row, "booster_fare", None), defaults.booster_fare),
        passenger_luggage_tiers=tuple(tiers),
    )


def defaults_public() -> dict[str, float | int | list[dict[str, int]]]:
    return DEFAULT_DISTANCE_INFANT_PRICING.to_public()
