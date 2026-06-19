from __future__ import annotations

import os
import random
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.lib.viator_allowed_products import (
    VIATOR_CITY_TO_CRUISE_PRODUCT_CODES,
    pick_random_allowed_viator_product_code,
)

VIATOR_TEST_SUBJECT_MARKER = (
    os.getenv("VIATOR_TEST_SUBJECT_MARKER") or "BR-TEST"
).strip() or "BR-TEST"

_VIATOR_TEST_SUBJECT = re.compile(
    rf"^(?:Re:\s*)?New Booking for (.+?) \(#{re.escape(VIATOR_TEST_SUBJECT_MARKER)}\)\s*$",
    re.IGNORECASE,
)


def get_booking_time_zone() -> str:
    return (os.getenv("TZ") or "Europe/Madrid").strip() or "Europe/Madrid"


def is_viator_test_booking_subject(subject: str) -> bool:
    return bool(_VIATOR_TEST_SUBJECT.match(subject.strip()))


def parse_viator_test_booking_subject(
    subject: str,
) -> dict[str, str] | None:
    match = _VIATOR_TEST_SUBJECT.match(subject.strip())
    if not match:
        return None
    return {
        "pickupDateLabel": match.group(1).strip(),
        "templateMarker": VIATOR_TEST_SUBJECT_MARKER.upper(),
    }


def generate_viator_test_booking_reference() -> str:
    suffix = f"{int(time.time() * 1000)}{random.randint(0, 999)}"[-10:]
    return f"BR-{suffix}"


def default_test_pickup_date_label() -> str:
    future = datetime.now(ZoneInfo(get_booking_time_zone())) + timedelta(days=7)
    return f"{future.strftime('%a')}, {future.day} {future.strftime('%b %Y')}"


def build_viator_test_email_subject(pickup_date_label: str | None = None) -> str:
    label = (pickup_date_label or "").strip() or default_test_pickup_date_label()
    return f"New Booking for {label} (#{VIATOR_TEST_SUBJECT_MARKER})"


def build_viator_test_email_bodies(
    *,
    booking_reference: str,
    pickup_date_label: str | None = None,
    product_code: str | None = None,
    sent_at: datetime | None = None,
) -> dict[str, str]:
    sent = sent_at or datetime.utcnow()
    label = (pickup_date_label or "").strip() or default_test_pickup_date_label()
    reference = booking_reference.strip().upper()
    code = (product_code or pick_random_allowed_viator_product_code()).strip().upper()

    text = "\n".join(
        [
            "Viator Test Booking",
            "",
            f"Booking Reference: {reference}",
            f"Product Code: {code}",
            f"Travel Date: {label}",
            "Tour Name: Barcelona Airport Transfer (TEST)",
            "Lead Traveler Name: Test Traveler",
            "Travelers: 2",
            "Tour Language: English",
            "Hotel Pickup: Barcelona El Prat Airport (TEST)",
            "Arrival Flight No: XX9999",
            "Arrival Airline: Test Air",
            "Drop Off Location: Hotel Arts Barcelona (TEST)",
            "Phone: +34600111222",
            "Email: viator.test@example.com",
            "",
            f"Sent at: {sent.isoformat()}Z",
        ]
    )

    html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif">
<h2>Viator Test Booking</h2>
<p><b>Booking Reference:</b> {reference}</p>
<p><b>Product Code:</b> {code}</p>
<p><b>Travel Date:</b> {label}</p>
<p><b>Tour Name:</b> Barcelona Airport Transfer (TEST)</p>
<p><b>Lead Traveler Name:</b> Test Traveler</p>
<p><b>Travelers:</b> 2</p>
<p><b>Tour Language:</b> English</p>
<p><b>Hotel Pickup:</b> Barcelona El Prat Airport (TEST)</p>
<p><b>Arrival Flight No:</b> XX9999</p>
<p><b>Arrival Airline:</b> Test Air</p>
<p><b>Drop Off Location:</b> Hotel Arts Barcelona (TEST)</p>
<p><b>Phone:</b> +34600111222</p>
<p><b>Email:</b> viator.test@example.com</p>
</body></html>"""

    return {"text": text, "html": html, "product_code": code}


def build_viator_test_cruise_ship_email_bodies(
    *,
    booking_reference: str,
    pickup_date_label: str | None = None,
    product_code: str | None = None,
    cruise_ship_name: str | None = None,
    sent_at: datetime | None = None,
) -> dict[str, str]:
    sent = sent_at or datetime.utcnow()
    label = (pickup_date_label or "").strip() or default_test_pickup_date_label()
    reference = booking_reference.strip().upper()
    code = (
        (product_code or VIATOR_CITY_TO_CRUISE_PRODUCT_CODES[0]).strip().upper()
    )
    ship = (cruise_ship_name or "Celebrity Equinox").strip() or "Celebrity Equinox"

    text = "\n".join(
        [
            "Viator Test Booking",
            "",
            f"Booking Reference: {reference}",
            f"Product Code: {code}",
            f"Travel Date: {label}",
            "Tour Name: Barcelona City to Cruise Port Transfer (TEST)",
            "Lead Traveler Name: Test Cruise Traveler",
            "Travelers: 2",
            "Tour Language: English",
            "Hotel Pickup: Hotel SERHS Ravoli Rambla La Rambla, 128 08002 (TEST)",
            "Departure Time: 10:00 am",
            f"Cruise Ship: {ship}",
            "Phone: +34600111222",
            "Email: viator.test@example.com",
            "",
            f"Sent at: {sent.isoformat()}Z",
        ]
    )

    html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif">
<h2>Viator Test Booking</h2>
<p><b>Booking Reference:</b> {reference}</p>
<p><b>Product Code:</b> {code}</p>
<p><b>Travel Date:</b> {label}</p>
<p><b>Tour Name:</b> Barcelona City to Cruise Port Transfer (TEST)</p>
<p><b>Lead Traveler Name:</b> Test Cruise Traveler</p>
<p><b>Travelers:</b> 2</p>
<p><b>Tour Language:</b> English</p>
<p><b>Hotel Pickup:</b> Hotel SERHS Ravoli Rambla La Rambla, 128 08002 (TEST)</p>
<p><b>Departure Time:</b> 10:00 am</p>
<p><b>Cruise Ship:</b> {ship}</p>
<p><b>Phone:</b> +34600111222</p>
<p><b>Email:</b> viator.test@example.com</p>
</body></html>"""

    return {"text": text, "html": html, "product_code": code}
