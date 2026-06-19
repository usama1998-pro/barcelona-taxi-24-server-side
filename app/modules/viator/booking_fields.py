from __future__ import annotations

from typing import TypedDict


class ViatorBookingDetails(TypedDict, total=False):
    productName: str
    leadTraveler: str
    travelerNames: str
    phone: str
    email: str
    pickupLocation: str
    dropoffLocation: str
    cruiseShipName: str
    travelers: str
    language: str
    specialRequirements: str
    arrivalFlightNo: str
    arrivalAirline: str
    disembarkationTime: str
    departureFlightNo: str
    departureTime: str
    departureAirline: str
    tourGrade: str
    tourGradeCode: str
    productCode: str


def merge_booking_fields(base: ViatorBookingDetails) -> ViatorBookingDetails:
    out: ViatorBookingDetails = {}
    for key, value in base.items():
        if key == "emailText":
            continue
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()  # type: ignore[literal-required]
    return out
