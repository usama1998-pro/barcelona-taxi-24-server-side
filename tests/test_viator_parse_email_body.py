from __future__ import annotations

from app.modules.viator.parse_email_body import _extract_from_text
from app.modules.viator.to_booking_mapper import (
    map_viator_to_create_booking_dto,
    resolve_viator_dropoff_location_label,
    resolve_viator_pickup_location_label,
)

SANDRA_BOOKING_EMAIL = """
Booking Reference: BR-1413674381
Travel Date: Sun, Aug 02, 2026
Lead Traveler Name: Sandra Egharevba
Traveler Names: Sandra Egharevba, Yolanda Wilkerson
Travelers: 2 Adults
Product Code: 406570P62
Tour Grade: Private Transfer from Barcelona hotels to Barcelona Cruise Port 11:00
Tour Grade Code: TG1~11:00
Tour Grade Description: Pickup included
Tour Language: English - Guide
Location: Barcelona, Spain
Net Rate: EUR €45,00
Hotel Pickup: Hampton By Hilton Barcelona Fira Gran Via, Plaza De Europa 33, 08908 L'Hospitalet de Llobregat Spain
Cruise Ship: Royal Caribbean Legend of the Seas
Pick up Location: Hampton By Hilton Barcelona Fira Gran Via, Plaza De Europa 33
Boarding Time: 12:00
"""


def test_cruise_ship_not_contaminated_by_pick_up_location_label() -> None:
    fields = _extract_from_text(SANDRA_BOOKING_EMAIL)

    assert fields["productCode"] == "406570P62"
    assert fields["cruiseShipName"] == "Royal Caribbean Legend of the Seas"
    assert fields["pickupLocation"] == "Hampton By Hilton Barcelona Fira Gran Via"
    assert resolve_viator_pickup_location_label(fields) == (
        "Hampton By Hilton Barcelona Fira Gran Via"
    )
    assert resolve_viator_dropoff_location_label(fields) == (
        "Royal Caribbean Legend of the Seas"
    )


def test_sandra_booking_email_maps_pickup_and_dropoff_correctly() -> None:
    fields = _extract_from_text(SANDRA_BOOKING_EMAIL)
    dto = map_viator_to_create_booking_dto(
        {
            "viatorReference": "BR-1413674381",
            "pickupDateLabel": "Sun, Aug 02, 2026",
            "details": fields,
        }
    )

    assert dto["pickupLocation"] == {
        "kind": "location",
        "label": "Hampton By Hilton Barcelona Fira Gran Via",
    }
    assert dto["dropoffLocation"] == {
        "kind": "location",
        "label": "Royal Caribbean Legend of the Seas",
    }
