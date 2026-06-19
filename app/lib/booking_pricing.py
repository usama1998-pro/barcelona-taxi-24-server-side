from __future__ import annotations

from dataclasses import dataclass

PASSENGER_LUGGAGE_RATE_TIERS = [
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

MAX_TIER_PRICE = PASSENGER_LUGGAGE_RATE_TIERS[-1]["price"]
INFANT_CARRIER_FARE = 7
CHILD_SEAT_FARE = 7
BOOSTER_FARE = 7
DISTANCE_SHORT_TRIP_MAX_KM = 17
DISTANCE_MID_RATE_EUR_PER_KM = 4
DISTANCE_MID_MAX_KM = 32
DISTANCE_LONG_RATE_EUR_PER_KM = 2


@dataclass(frozen=True)
class BookingPriceInputs:
    passenger_count: int
    luggage_count: int
    infant_carrier_count: int
    child_seat_count: int
    booster_count: int
    is_return_trip: bool = False
    distance_km: float | None = None


def calculate_passenger_luggage_fare(passenger_count: int, luggage_count: int) -> int:
    passengers = max(1, int(passenger_count))
    luggage = max(0, int(luggage_count))
    effective_luggage = luggage if luggage > 0 else 1

    fitting = [
        tier
        for tier in PASSENGER_LUGGAGE_RATE_TIERS
        if tier["passengers"] >= passengers and tier["luggage"] >= effective_luggage
    ]
    if not fitting:
        return MAX_TIER_PRICE
    return min(tier["price"] for tier in fitting)


def calculate_distance_surcharge(distance_km: float) -> float:
    km = max(0.0, distance_km)
    if km < DISTANCE_SHORT_TRIP_MAX_KM:
        return 0.0
    if km <= DISTANCE_MID_MAX_KM:
        return km * DISTANCE_MID_RATE_EUR_PER_KM
    return km * DISTANCE_LONG_RATE_EUR_PER_KM


def calculate_booking_price(input_data: BookingPriceInputs) -> int:
    infant_extra = max(0, input_data.infant_carrier_count) * INFANT_CARRIER_FARE
    child_extra = max(0, input_data.child_seat_count) * CHILD_SEAT_FARE
    booster_extra = max(0, input_data.booster_count) * BOOSTER_FARE
    seat_extras = infant_extra + child_extra + booster_extra

    tier_fare = calculate_passenger_luggage_fare(
        input_data.passenger_count,
        input_data.luggage_count,
    )
    distance_fare = 0.0
    if (
        input_data.distance_km is not None
        and input_data.distance_km >= DISTANCE_SHORT_TRIP_MAX_KM
    ):
        distance_fare = calculate_distance_surcharge(input_data.distance_km)

    one_way_total = tier_fare + distance_fare + seat_extras
    total = one_way_total * 2 if input_data.is_return_trip else one_way_total
    return round(total)
