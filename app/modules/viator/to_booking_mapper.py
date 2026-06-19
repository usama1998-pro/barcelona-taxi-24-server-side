from __future__ import annotations

import re
from typing import Any

from app.common.utils.phone import normalize_phone_number
from app.lib.viator_allowed_products import is_city_to_cruise_product_code
from app.modules.viator.booking_fields import ViatorBookingDetails
from app.modules.viator.parse_scheduled_time import (
    parse_viator_passenger_count,
    parse_viator_scheduled_time_iso,
    viator_guest_email,
)

AIRPORT_PATTERN = re.compile(r"airport|el prat|aeropuerto", re.IGNORECASE)
DB_STRING_MAX = 191


def _truncate_db_string(value: str | None, max_len: int = DB_STRING_MAX) -> str | None:
    if not value:
        return None
    trimmed = value.strip()
    if len(trimmed) <= max_len:
        return trimmed
    if max_len <= 1:
        return trimmed[:max_len]
    return f"{trimmed[: max_len - 1]}…"


def _to_pickup_location_json(
    label: str | None,
    fallback: str,
    arrival: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    text = (label or fallback)[:500]
    if AIRPORT_PATTERN.search(text):
        location: dict[str, Any] = {
            "kind": "airport",
            "label": text if "Airport" in text else "Barcelona-El Prat Airport",
        }
        airline = (arrival or {}).get("airline")
        flight = (arrival or {}).get("flightNo")
        if airline:
            location["airline"] = airline.strip()
        if flight:
            location["flight"] = flight.strip()
        return location
    return {"kind": "location", "label": text}


def _to_dropoff_location_json(
    label: str | None,
    fallback: str,
    *,
    force_airport: bool = False,
    airline: str | None = None,
    flight_no: str | None = None,
    departure_time: str | None = None,
) -> dict[str, Any]:
    text = (label or fallback)[:500]
    is_airport = force_airport or bool(AIRPORT_PATTERN.search(text))
    if is_airport:
        location: dict[str, Any] = {
            "kind": "airport",
            "label": text if "Airport" in text else "Barcelona-El Prat Airport",
        }
        if airline:
            location["airline"] = airline
        if flight_no:
            location["flight"] = flight_no
        if departure_time:
            location["departureTime"] = departure_time
        return location
    return {"kind": "location", "label": text}


def _looks_like_invalid_person_name(value: str) -> bool:
    if len(value) > 120:
        return True
    return bool(
        re.search(
            r"\b(adults?|children|infants?|transfer|airport|viator|pickup|tour)\b",
            value,
            re.IGNORECASE,
        )
    )


def _resolve_lead_traveler_customer_name(details: ViatorBookingDetails) -> str:
    lead = (details.get("leadTraveler") or "").strip()
    if lead and not _looks_like_invalid_person_name(lead):
        return lead
    traveler_names = details.get("travelerNames") or ""
    first_listed = next(
        (part.strip() for part in re.split(r"[,;]", traveler_names) if part.strip()),
        None,
    )
    if first_listed and not _looks_like_invalid_person_name(first_listed):
        return first_listed
    return "Viator guest"


def _is_airport_pickup(details: ViatorBookingDetails) -> bool:
    return bool(AIRPORT_PATTERN.search(details.get("pickupLocation") or ""))


def resolve_viator_pickup_location_label(details: ViatorBookingDetails) -> str | None:
    if not is_city_to_cruise_product_code(details.get("productCode")):
        return details.get("pickupLocation")
    return (details.get("cruiseShipName") or "").strip() or details.get("pickupLocation")


def resolve_viator_dropoff_location_label(details: ViatorBookingDetails) -> str | None:
    if not is_city_to_cruise_product_code(details.get("productCode")):
        return details.get("dropoffLocation")
    return (details.get("cruiseShipName") or "").strip() or details.get("dropoffLocation")


def _build_flight_info(details: ViatorBookingDetails) -> dict[str, str | None]:
    if _is_airport_pickup(details):
        return {
            "airline": (details.get("arrivalAirline") or "").strip() or None,
            "flightNo": (details.get("arrivalFlightNo") or "").strip() or None,
        }
    return {
        "airline": (details.get("departureAirline") or details.get("arrivalAirline") or "").strip()
        or None,
        "flightNo": (details.get("departureFlightNo") or details.get("arrivalFlightNo") or "").strip()
        or None,
    }


def _build_flight_number(details: ViatorBookingDetails) -> str | None:
    flight = _build_flight_info(details)
    parts = [part for part in [flight.get("airline"), flight.get("flightNo")] if part]
    return " ".join(parts) if parts else None


def _build_airport_dropoff_return_time_iso(
    pickup_date_label: str,
    details: ViatorBookingDetails,
) -> str | None:
    departure = (details.get("departureTime") or "").strip()
    if not departure:
        return None
    parsed = parse_viator_scheduled_time_iso(pickup_date_label, departure)
    return parsed["iso"] if parsed["hasTime"] else None


def map_viator_to_create_booking_dto(input_data: dict[str, Any]) -> dict[str, Any]:
    viator_reference = input_data["viatorReference"]
    pickup_date_label = input_data["pickupDateLabel"]
    details: ViatorBookingDetails = input_data["details"]

    phone = normalize_phone_number((details.get("phone") or "").strip() or "+34000000000")
    customer_name = _resolve_lead_traveler_customer_name(details)
    airport_pickup = _is_airport_pickup(details)
    city_to_cruise = is_city_to_cruise_product_code(details.get("productCode"))
    dropoff_at_airport = bool(
        re.search(r"airport|el prat|aeropuerto", details.get("dropoffLocation") or "", re.IGNORECASE)
    )
    flight = _build_flight_info(details)
    pickup_label = resolve_viator_pickup_location_label(details)
    dropoff_label = resolve_viator_dropoff_location_label(details)
    dropoff_airport_return_time = (
        _build_airport_dropoff_return_time_iso(pickup_date_label, details)
        if dropoff_at_airport
        else None
    )

    scheduled = parse_viator_scheduled_time_iso(
        pickup_date_label,
        {
            "departureTime": details.get("departureTime"),
            "tourGradeCode": details.get("tourGradeCode"),
            "isAirportPickup": airport_pickup,
            "preferTourGradeCodeTime": dropoff_at_airport or city_to_cruise,
        },
    )
    passenger_count = parse_viator_passenger_count(details.get("travelers"))

    note_parts: list[str] = []
    if not scheduled["hasTime"]:
        note_parts.append("No pickup time selected by customer")
    special_reqs = _truncate_db_string((details.get("specialRequirements") or "").strip() or None)
    if special_reqs:
        note_parts.append(special_reqs)
    note = _truncate_db_string(" | ".join(note_parts)) if note_parts else None

    return {
        "bookingReference": viator_reference,
        "customerName": _truncate_db_string(customer_name),
        "customerEmail": _truncate_db_string(
            (details.get("email") or "").strip() or viator_guest_email(viator_reference)
        ),
        "customerPhone": _truncate_db_string(phone),
        "pickupLocation": _to_pickup_location_json(pickup_label, "Pickup TBC", flight),
        "dropoffLocation": _to_dropoff_location_json(
            dropoff_label,
            "Drop-off TBC",
            force_airport=dropoff_at_airport,
            airline=(details.get("departureAirline") or "").strip() if dropoff_at_airport else None,
            flight_no=(details.get("departureFlightNo") or "").strip() if dropoff_at_airport else None,
            departure_time=(details.get("departureTime") or "").strip() if dropoff_at_airport else None,
        ),
        "returnTime": dropoff_airport_return_time,
        "scheduledTime": scheduled["iso"],
        "price": 0,
        "status": "PENDING",
        "luggageCount": 0,
        "passengerCount": passenger_count,
        "flightNumber": _truncate_db_string(_build_flight_number(details)),
        "note": note,
    }
