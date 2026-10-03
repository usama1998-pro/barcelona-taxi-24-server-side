"""HTML email templates for booking notifications (client + owner)."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.lib.booking_source import is_website_booking_public

BRAND_NAME = "BarcelonaTaxi24"
BRAND_COLOR = "#0fb896"
BRAND_DARK = "#0a8f74"
SITE_URL = "https://barcelonataxi24.com"
SITE_DISPLAY = "www.barcelonataxi24.com"


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _booking_time_zone() -> str:
    return (os.getenv("TZ") or "Europe/Madrid").strip() or "Europe/Madrid"


def _location_label(location: dict[str, Any] | None) -> str:
    if not location:
        return "—"
    for key in ("label", "address"):
        value = location.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "—"


def _format_scheduled_time(iso: str | datetime) -> str:
    date = iso if isinstance(iso, datetime) else datetime.fromisoformat(
        iso.replace("Z", "+00:00")
    )
    tz = ZoneInfo(_booking_time_zone())
    return date.astimezone(tz).strftime("%d %b %Y, %H:%M")


def _format_fare_eur(price: float) -> str:
    return f"€{price:,.2f}"


def _format_child_seats_summary(booking: dict[str, Any]) -> str | None:
    parts: list[str] = []
    if booking.get("infantCarrierCount", 0) > 0:
        count = booking["infantCarrierCount"]
        parts.append(f"{count} infant carrier{'s' if count != 1 else ''}")
    if booking.get("childSeatCount", 0) > 0:
        count = booking["childSeatCount"]
        parts.append(f"{count} child seat{'s' if count != 1 else ''}")
    if booking.get("boosterCount", 0) > 0:
        count = booking["boosterCount"]
        parts.append(f"{count} booster{'s' if count != 1 else ''}")
    return ", ".join(parts) if parts else None


def _normalize_email(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if not normalized or "@" not in normalized:
        return None
    return normalized


def booking_customer_email(
    booking: dict[str, Any],
    *,
    override: str | None = None,
) -> str | None:
    for candidate in (
        override,
        booking.get("customerEmail"),
        (
            (booking.get("user") or {}).get("email")
            if isinstance(booking.get("user"), dict)
            else None
        ),
    ):
        normalized = _normalize_email(str(candidate) if candidate is not None else None)
        if normalized:
            return normalized
    return None


def _detail_rows(booking: dict[str, Any], *, for_owner: bool) -> list[tuple[str, str]]:
    user = booking.get("user") or {}
    customer_name = (booking.get("customerName") or user.get("fullName") or "—").strip()
    customer_email = booking_customer_email(booking) or "—"
    customer_phone = (booking.get("customerPhone") or user.get("phone") or "—").strip()
    pickup = _location_label(booking.get("pickupLocation"))
    dropoff = _location_label(booking.get("dropoffLocation"))
    scheduled = _format_scheduled_time(booking["scheduledTime"])
    return_time = booking.get("returnTime")
    child_seats = _format_child_seats_summary(booking)
    flight = (booking.get("flightNumber") or "").strip() or None
    note = (booking.get("note") or "").strip() or None
    driver = ((booking.get("driver") or {}).get("name") or "").strip() or None

    rows: list[tuple[str, str]] = [
        ("Reference", str(booking["bookingReference"])),
        ("Passenger", customer_name),
    ]
    if for_owner:
        rows.append(("Email", customer_email))
        rows.append(("Phone", customer_phone))
    rows.extend(
        [
            ("Pickup", pickup),
            ("Drop-off", dropoff),
            ("Pickup date & time", scheduled),
        ]
    )
    if return_time:
        rows.append(("Return date & time", _format_scheduled_time(return_time)))
    rows.append(("Passengers", str(booking["passengerCount"])))
    if is_website_booking_public(booking):
        rows.append(("Luggage pieces", str(booking["luggageCount"])))
        if child_seats:
            rows.append(("Child seats", child_seats))
    if flight:
        rows.append(("Flight number", flight))
    if note:
        rows.append(("Notes", note))
    if driver:
        rows.append(("Driver", driver))
    rows.append(("Total fare", _format_fare_eur(float(booking["price"]))))
    rows.append(("Status", str(booking["status"])))
    return rows


def _rows_html(rows: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for index, (label, value) in enumerate(rows):
        bg = "#f8fafc" if index % 2 == 0 else "#ffffff"
        parts.append(
            f"""
            <tr>
              <td style="padding:12px 14px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:13px;font-weight:600;width:38%;background:{bg};vertical-align:top;">
                {_escape_html(label)}
              </td>
              <td style="padding:12px 14px;border-bottom:1px solid #e2e8f0;color:#0f172a;font-size:14px;background:{bg};vertical-align:top;">
                {_escape_html(value)}
              </td>
            </tr>
            """
        )
    return "".join(parts)


def _email_shell(
    *,
    preheader: str,
    eyebrow: str,
    title: str,
    intro_html: str,
    rows: list[tuple[str, str]],
    footer_note: str,
    accent: str = BRAND_COLOR,
) -> str:
    safe_preheader = _escape_html(preheader)
    safe_eyebrow = _escape_html(eyebrow)
    safe_title = _escape_html(title)
    safe_footer = _escape_html(footer_note)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
</head>
<body style="margin:0;padding:0;background:#eef2f6;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{safe_preheader}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f6;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #dbe3ea;">
          <tr>
            <td style="background:{accent};padding:28px 24px;">
              <p style="margin:0 0 8px;color:rgba(255,255,255,0.88);font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">{safe_eyebrow}</p>
              <h1 style="margin:0;color:#ffffff;font-size:24px;line-height:1.25;font-weight:700;">{safe_title}</h1>
              <p style="margin:10px 0 0;color:rgba(255,255,255,0.92);font-size:14px;">{_escape_html(BRAND_NAME)}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:24px;">
              {intro_html}
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
                {_rows_html(rows)}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:0 24px 24px;">
              <p style="margin:0;padding:14px 16px;background:#f1f5f9;border-radius:10px;color:#475569;font-size:13px;line-height:1.5;">
                {safe_footer}
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 24px;background:#0f172a;text-align:center;">
              <p style="margin:0 0 6px;color:#ffffff;font-size:13px;font-weight:700;">{_escape_html(BRAND_NAME)}</p>
              <p style="margin:0;">
                <a href="{SITE_URL}" style="color:{accent};font-size:12px;text-decoration:none;">{SITE_DISPLAY}</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_client_booking_confirmation_html(booking: dict[str, Any] | None) -> str:
    if not booking:
        return _email_shell(
            preheader="Your taxi booking was received successfully.",
            eyebrow="Booking confirmed",
            title="Thank you for your booking",
            intro_html=(
                "<p style='margin:0 0 16px;color:#334155;font-size:15px;line-height:1.6;'>"
                "Your taxi booking was received successfully. We will contact you if anything changes."
                "</p>"
            ),
            rows=[("Status", "Received")],
            footer_note="Keep this email for your records. Reply if you need to change your trip.",
        )

    reference = str(booking.get("bookingReference") or "your booking")
    user = booking.get("user") or {}
    customer_name = (booking.get("customerName") or user.get("fullName") or "there").strip()
    rows = _detail_rows(booking, for_owner=False)
    intro = f"""
      <p style="margin:0 0 8px;color:#334155;font-size:15px;line-height:1.6;">
        Hi {_escape_html(customer_name)},
      </p>
      <p style="margin:0 0 16px;color:#334155;font-size:15px;line-height:1.6;">
        Thank you for booking with {_escape_html(BRAND_NAME)}. Your transfer
        <strong>{_escape_html(reference)}</strong> is confirmed. Trip details are below.
      </p>
    """
    return _email_shell(
        preheader=f"Booking {reference} confirmed — {_format_fare_eur(float(booking['price']))}",
        eyebrow="Booking confirmed",
        title="Your taxi is booked",
        intro_html=intro,
        rows=rows,
        footer_note=(
            "Please arrive a few minutes early at the pickup point. "
            "Reply to this email if you need help with your booking."
        ),
    )


def render_owner_new_booking_html(booking: dict[str, Any]) -> str:
    reference = str(booking["bookingReference"])
    user = booking.get("user") or {}
    customer_name = (booking.get("customerName") or user.get("fullName") or "Customer").strip()
    fare = _format_fare_eur(float(booking["price"]))
    rows = _detail_rows(booking, for_owner=True)
    intro = f"""
      <p style="margin:0 0 16px;color:#334155;font-size:15px;line-height:1.6;">
        A new website booking was just created for
        <strong>{_escape_html(customer_name)}</strong>
        ({_escape_html(fare)}). Full customer and trip details are below.
      </p>
    """
    return _email_shell(
        preheader=f"New booking {reference} — {customer_name} — {fare}",
        eyebrow="New booking alert",
        title=f"Booking {reference}",
        intro_html=intro,
        rows=rows,
        footer_note="This alert was sent automatically from the booking API.",
        accent="#2563eb",
    )
