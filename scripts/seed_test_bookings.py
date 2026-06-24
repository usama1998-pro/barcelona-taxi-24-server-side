"""
Creates test bookings that mimic the public website and the driver app payloads.

Usage:
  python -m scripts.seed_test_bookings
  python -m scripts.seed_test_bookings --website
  python -m scripts.seed_test_bookings --app
  python -m scripts.seed_test_bookings --http

By default uses the bookings service + database directly (works on production
shared hosting where localhost HTTP is unavailable). Pass --http to POST via
APP_URL/API_BASE_URL instead (local API must be running).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.lib.booking_pricing import BookingPriceInputs, calculate_booking_price
from app.lib.mail_config import get_booking_notify_email
from app.modules.bookings.schemas import CreateBookingBody
from app.modules.bookings.service import bookings_service
from scripts._bootstrap import api_base_url, app_url_looks_local, bootstrap, db_session

BARCELONA_AIRPORT = "Barcelona-El Prat International Airport (BCN)"
AIRPORT_LABEL = re.compile(
    r"^barcelona[- ]?el\s+prat|barcelona.*\(bcn\)|\bbcn\b",
    re.IGNORECASE,
)


def is_airport_label(label: str) -> bool:
    trimmed = label.strip()
    if not trimmed:
        return False
    if AIRPORT_LABEL.search(trimmed):
        return True
    return bool(re.search(r"airport|aeropuerto", trimmed, re.IGNORECASE))


def build_booking_location(
    label: str,
    *,
    flight: str | None = None,
    airline: str | None = None,
) -> dict:
    trimmed = label.strip()
    flight_value = (flight or "").strip()
    airline_value = (airline or "").strip()

    if is_airport_label(trimmed):
        location = {"kind": "airport", "label": trimmed}
        if flight_value:
            location["flight"] = flight_value
        if airline_value:
            location["airline"] = airline_value
        return location

    return {"kind": "location", "label": trimmed or "Address TBC"}


def build_booking_locations(
    quote: dict[str, str],
    flight: str | None = None,
) -> tuple[dict, dict]:
    trimmed_flight = (flight or "").strip()
    pickup_is_airport = quote["routeType"] == "fromAirport" or is_airport_label(
        quote["pickup"]
    )
    dropoff_is_airport = quote["routeType"] == "toAirport" or is_airport_label(
        quote["dropoff"]
    )

    if trimmed_flight and pickup_is_airport and not dropoff_is_airport:
        return (
            build_booking_location(quote["pickup"], flight=trimmed_flight),
            build_booking_location(quote["dropoff"]),
        )
    if trimmed_flight and dropoff_is_airport:
        return (
            build_booking_location(quote["pickup"]),
            build_booking_location(quote["dropoff"], flight=trimmed_flight),
        )

    return (
        build_booking_location(quote["pickup"]),
        build_booking_location(quote["dropoff"]),
    )


def guest_email_from_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    core = digits if digits else "unknown"
    return f"guest.{core}@taxibarcelona24.guest"


def pickup_iso(hours_from_now: int = 48) -> str:
    scheduled = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    scheduled = scheduled.replace(minute=0, second=0, microsecond=0)
    return scheduled.isoformat().replace("+00:00", "Z")


def estimate_website_price(
    passengers: int,
    luggage: int,
    infant: int = 0,
    child: int = 0,
    booster: int = 0,
) -> int:
    return calculate_booking_price(
        BookingPriceInputs(
            passenger_count=passengers,
            luggage_count=luggage,
            infant_carrier_count=infant,
            child_seat_count=child,
            booster_count=booster,
        )
    )


def website_test_customer_email() -> str:
    override = (os.getenv("SEED_TEST_CUSTOMER_EMAIL") or "").strip().lower()
    if override:
        return override
    notify = get_booking_notify_email()
    if notify:
        return notify
    return "website.test@barcelonataxi24.com"


def build_website_payload(scheduled_time: str) -> dict:
    quote = {
        "routeType": "fromAirport",
        "pickup": BARCELONA_AIRPORT,
        "dropoff": "Hotel Arts Barcelona, Carrer de la Marina, 19-21",
    }
    flight = "VY1451"
    pickup_location, dropoff_location = build_booking_locations(quote, flight)
    return {
        "customerName": "Website Test Passenger",
        "customerEmail": website_test_customer_email(),
        "customerPhone": "+34 600 111 222",
        "flightNumber": flight,
        "pickupLocation": pickup_location,
        "dropoffLocation": dropoff_location,
        "scheduledTime": scheduled_time,
        "price": estimate_website_price(2, 2, 1, 0, 0),
        "status": "PENDING",
        "luggageCount": 2,
        "passengerCount": 2,
        "infantCarrierCount": 1,
        "childSeatCount": 0,
        "boosterCount": 0,
        "note": (
            "Wheelchair accessible vehicle: Test booking from seed-test-bookings "
            "script (website)."
        ),
    }


def build_app_payload(scheduled_time: str) -> dict:
    phone = "+34600222333"
    return {
        "customerName": "App Test Passenger",
        "customerPhone": phone,
        "customerEmail": guest_email_from_phone(phone),
        "pickupLocation": {
            "kind": "airport",
            "label": "Barcelona-El Prat Airport",
            "airline": "Vueling",
            "flight": "VY9999",
        },
        "dropoffLocation": {
            "kind": "location",
            "label": "Plaça de Catalunya, Barcelona",
        },
        "flightNumber": "Vueling VY9999",
        "scheduledTime": scheduled_time,
        "price": 0,
        "status": "PENDING",
        "luggageCount": 0,
        "passengerCount": 3,
        "infantCarrierCount": 0,
        "childSeatCount": 0,
        "boosterCount": 0,
        "note": "Test booking from seed-test-bookings script (driver app).",
    }


def _format_http_error(error: urllib.error.HTTPError) -> str:
    raw = error.read().decode("utf-8", errors="replace")
    try:
        parsed = json.loads(raw)
        message = parsed.get("message") or parsed.get("detail")
        if isinstance(message, list):
            return " ".join(str(item) for item in message)
        if message:
            return str(message)
    except json.JSONDecodeError:
        pass
    return raw or str(error)


def post_booking(base_url: str, body: dict) -> dict:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/bookings",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(_format_http_error(error)) from error
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", error)
        raise RuntimeError(
            f"Could not reach API at {base_url}/bookings ({reason}). "
            "On production, run without --http (default uses the database directly), "
            "or set APP_URL / API_BASE_URL to your public API URL."
        ) from error


def create_booking_direct(body: dict) -> dict:
    dto = CreateBookingBody.model_validate(body)
    with db_session() as session:
        try:
            return bookings_service.create(session, dto)
        except HTTPException as error:
            detail = error.detail
            if isinstance(detail, list):
                text = " ".join(str(item) for item in detail)
            else:
                text = str(detail)
            raise RuntimeError(text) from error


def expected_icon(source: str) -> str:
    return "globe (website)" if source == "website" else "phone-portrait (app)"


def _print_seed_result(created: dict, source: str, body: dict) -> None:
    email = body.get("customerEmail") or created.get("customerEmail") or "—"
    print(f"  reference:  {created['bookingReference']}")
    print(f"  uuid:       {created['uuid']}")
    print(f"  email:      {email}")
    print(f"  app icon:   {expected_icon(source)}")
    notifications = created.get("notifications")
    if isinstance(notifications, dict):
        print(
            "  emails:     "
            f"customer={notifications.get('customerEmailSent')} "
            f"owner={notifications.get('ownerEmailSent')}"
        )


def seed_one_http(base_url: str, label: str, source: str, body: dict) -> None:
    print(f"\n--- {label} ---")
    created = post_booking(base_url, body)
    _print_seed_result(created, source, body)


def seed_one_direct(label: str, source: str, body: dict) -> None:
    print(f"\n--- {label} ---")
    created = create_booking_direct(body)
    _print_seed_result(created, source, body)


def use_http_mode(args: set[str]) -> bool:
    if "--http" in args:
        return True
    if "--direct" in args:
        return False
    from app.core.config import settings

    if settings.app_env == "production":
        return False
    return not app_url_looks_local()


def main() -> int:
    bootstrap()
    args = set(sys.argv[1:])
    website_only = "--website" in args
    app_only = "--app" in args
    both = not website_only and not app_only
    http_mode = use_http_mode(args)

    if http_mode:
        base_url = api_base_url()
        print(f"Mode: HTTP → {base_url}/bookings")
        seed = lambda label, source, body: seed_one_http(base_url, label, source, body)
    else:
        print("Mode: direct (bookings service + database)")
        if app_url_looks_local():
            print(
                "Note: APP_URL is localhost; direct mode avoids connection refused on production."
            )
        seed = seed_one_direct

    try:
        if both or website_only:
            seed(
                "Website booking (POST /bookings — same payload as barcelonataxi24.com)",
                "website",
                build_website_payload(pickup_iso(48)),
            )
        if both or app_only:
            seed(
                "App booking (guest email + airport JSON — same as New Reservation screen)",
                "app",
                build_app_payload(pickup_iso(50)),
            )
    except RuntimeError as error:
        print(error)
        return 1

    print("\nDone. Open the driver app bookings list to compare icons.")
    print("  globe  = website booking")
    print("  phone  = app booking")
    print("  mail   = Viator email (BR-…)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
