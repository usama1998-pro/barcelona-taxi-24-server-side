"""Repair cruise pickup labels on bookings imported before mapper fix.

Usage:
  python -m scripts.fix_cruise_pickup_bookings          # dry-run (list only)
  python -m scripts.fix_cruise_pickup_bookings --apply  # update DB
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.db.models.booking import Booking
from app.db.models.viator_alert import ViatorAlert
from app.db.session import _session_factory
from app.modules.viator.booking_fields import merge_booking_fields
from app.modules.viator.to_booking_mapper import (
    map_viator_to_create_booking_dto,
    resolve_viator_pickup_location_label,
)
from scripts._bootstrap import bootstrap


def _pickup_label(pickup_location: object) -> str:
    if isinstance(pickup_location, dict):
        return str(pickup_location.get("label") or "").strip()
    return str(pickup_location or "").strip()


def main() -> int:
    bootstrap()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write corrected pickup labels to the database",
    )
    args = parser.parse_args()

    session = _session_factory()()
    updated = 0
    checked = 0
    try:
        alerts = session.scalars(select(ViatorAlert)).all()
        for alert in alerts:
            payload = merge_booking_fields(dict(alert.payload or {}))
            product_code = payload.get("productCode")
            cruise_ship = (payload.get("cruiseShipName") or "").strip()
            if not cruise_ship:
                continue

            expected_label = resolve_viator_pickup_location_label(payload)
            if not expected_label or expected_label == (payload.get("pickupLocation") or "").strip():
                continue

            booking = session.scalar(
                select(Booking).where(Booking.booking_reference == alert.viator_reference)
            )
            if not booking:
                continue

            checked += 1
            current_label = _pickup_label(booking.pickup_location)
            if current_label == expected_label:
                continue

            print(f"\n{alert.viator_reference} | {booking.customer_name}")
            print(f"  product: {product_code}")
            print(f"  cruise ship: {cruise_ship}")
            print(f"  pickup (was):  {current_label}")
            print(f"  pickup (fix):  {expected_label}")

            if args.apply:
                dto = map_viator_to_create_booking_dto(
                    {
                        "viatorReference": alert.viator_reference,
                        "pickupDateLabel": alert.pickup_date_label,
                        "details": payload,
                    }
                )
                booking.pickup_location = dto["pickupLocation"]
                updated += 1

        if args.apply:
            session.commit()
            print(f"\nUpdated {updated} booking(s).")
        else:
            print(f"\nChecked {checked} cruise pickup candidate(s). Re-run with --apply to fix.")
    except Exception as error:
        session.rollback()
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
