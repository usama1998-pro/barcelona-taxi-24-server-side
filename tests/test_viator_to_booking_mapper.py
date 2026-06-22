from __future__ import annotations

from app.modules.viator.to_booking_mapper import (
    map_viator_to_create_booking_dto,
    resolve_viator_dropoff_location_label,
    resolve_viator_pickup_location_label,
)


def test_cruise_to_city_uses_ship_name_in_pickup() -> None:
    details = {
        "productCode": "419333P8",
        "cruiseShipName": "MSC Meraviglia",
        "pickupLocation": "Port of Barcelona, Moll Adossat",
        "dropoffLocation": "Hotel Arts Barcelona",
        "leadTraveler": "Jane Cruise",
        "travelers": "2",
    }
    assert resolve_viator_pickup_location_label(details) == "MSC Meraviglia"
    assert resolve_viator_dropoff_location_label(details) == "Hotel Arts Barcelona"

    dto = map_viator_to_create_booking_dto(
        {
            "viatorReference": "BR-123456789",
            "pickupDateLabel": "Thu, Jun 12, 2026",
            "details": details,
        }
    )
    assert dto["pickupLocation"] == {"kind": "location", "label": "MSC Meraviglia"}
    assert dto["dropoffLocation"] == {"kind": "location", "label": "Hotel Arts Barcelona"}


def test_city_to_cruise_uses_ship_name_in_dropoff() -> None:
    details = {
        "productCode": "406570P62",
        "cruiseShipName": "Costa Smeralda",
        "pickupLocation": "Hotel Arts Barcelona",
        "dropoffLocation": "Port of Barcelona, Moll Adossat",
        "leadTraveler": "John Cruise",
        "travelers": "2",
    }
    assert resolve_viator_pickup_location_label(details) == "Hotel Arts Barcelona"
    assert resolve_viator_dropoff_location_label(details) == "Costa Smeralda"

    dto = map_viator_to_create_booking_dto(
        {
            "viatorReference": "BR-987654321",
            "pickupDateLabel": "Fri, Jun 13, 2026",
            "details": details,
        }
    )
    assert dto["pickupLocation"] == {"kind": "location", "label": "Hotel Arts Barcelona"}
    assert dto["dropoffLocation"] == {"kind": "location", "label": "Costa Smeralda"}


def test_cruise_port_to_airport_uses_ship_name_in_pickup() -> None:
    details = {
        "productCode": "406570P8",
        "cruiseShipName": "Norwegian Escape",
        "pickupLocation": "Port of Barcelona, Moll Adossat",
        "dropoffLocation": "Barcelona-El Prat Airport",
        "departureFlightNo": "VY1234",
        "departureAirline": "Vueling",
    }
    assert resolve_viator_pickup_location_label(details) == "Norwegian Escape"
    dto = map_viator_to_create_booking_dto(
        {
            "viatorReference": "BR-555666777",
            "pickupDateLabel": "Mon, Jul 6, 2026",
            "details": details,
        }
    )
    assert dto["pickupLocation"] == {"kind": "location", "label": "Norwegian Escape"}
    assert dto["dropoffLocation"]["kind"] == "airport"
