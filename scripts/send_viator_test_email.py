"""
Sends a Viator-style TEST email into the Hostinger mailbox.

Usage:
  python -m scripts.send_viator_test_email
  python -m scripts.send_viator_test_email --cruise-ship
  python -m scripts.send_viator_test_email --cruise-ship "MSC Meraviglia"
"""

from __future__ import annotations

import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.lib.mail_config import get_smtp_config
from app.lib.viator_test_email import (
    VIATOR_TEST_SUBJECT_MARKER,
    build_viator_test_cruise_ship_email_bodies,
    build_viator_test_email_bodies,
    build_viator_test_email_subject,
    default_test_pickup_date_label,
    generate_viator_test_booking_reference,
)
from scripts._bootstrap import bootstrap


def parse_cruise_ship_arg() -> str | None:
    if "--cruise-ship" not in sys.argv[1:]:
        return None
    index = sys.argv.index("--cruise-ship")
    if index + 1 < len(sys.argv) and not sys.argv[index + 1].startswith("--"):
        return sys.argv[index + 1]
    return ""


def main() -> int:
    bootstrap()
    smtp = get_smtp_config()
    if smtp is None:
        print(
            "SMTP not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASS in server-side/.env"
        )
        return 1

    cruise_ship_arg = parse_cruise_ship_arg()
    is_cruise_ship = cruise_ship_arg is not None
    pickup_date_label = default_test_pickup_date_label()
    booking_reference = generate_viator_test_booking_reference()
    subject = build_viator_test_email_subject(pickup_date_label)

    if is_cruise_ship:
        bodies = build_viator_test_cruise_ship_email_bodies(
            booking_reference=booking_reference,
            pickup_date_label=pickup_date_label,
            cruise_ship_name=cruise_ship_arg or None,
        )
    else:
        bodies = build_viator_test_email_bodies(
            booking_reference=booking_reference,
            pickup_date_label=pickup_date_label,
        )

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f'"{smtp.from_name}" <{smtp.user}>'
    message["To"] = smtp.user
    message.attach(MIMEText(bodies["text"], "plain", "utf-8"))
    message.attach(MIMEText(bodies["html"], "html", "utf-8"))

    if smtp.secure:
        with smtplib.SMTP_SSL(smtp.host, smtp.port) as client:
            client.login(smtp.user, smtp.password)
            client.send_message(message)
    else:
        with smtplib.SMTP(smtp.host, smtp.port) as client:
            client.starttls()
            client.login(smtp.user, smtp.password)
            client.send_message(message)

    print(
        "Viator test email sent (city → cruise port)."
        if is_cruise_ship
        else "Viator test email sent."
    )
    print(f"  To: {smtp.user}")
    print(f"  Subject: {subject}")
    print(f"  Marker: #{VIATOR_TEST_SUBJECT_MARKER}")
    print(f"  Booking reference (body): {booking_reference}")
    print(f"  Product code (body): {bodies['product_code']}")
    if is_cruise_ship:
        print(f"  Cruise ship: {cruise_ship_arg or 'Celebrity Equinox'}")
    print("")
    print(
        "Next: trigger POST /viator/inbox/check (cron or manual) to import into the database."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
