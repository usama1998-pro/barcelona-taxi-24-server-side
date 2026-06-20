from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models.booking import Booking
from app.lib.booking_source import is_website_booking_public
from app.modules.bookings.serializers import to_public_booking
from app.lib.mail_config import (
    SmtpConfig,
    get_booking_notify_email,
    get_smtp_config,
    is_smtp_configured,
)

logger = logging.getLogger(__name__)


def _booking_time_zone() -> str:
    return (os.getenv("TZ") or "Europe/Madrid").strip() or "Europe/Madrid"


def _serialize_public_booking(booking: Booking) -> dict[str, Any]:
    return to_public_booking(booking)


def find_one_public_by_uuid(session: Session, uuid: str) -> dict[str, Any]:
    booking = session.scalar(
        select(Booking)
        .options(joinedload(Booking.user), joinedload(Booking.driver))
        .where(Booking.uuid == uuid, Booking.deleted_at.is_(None))
    )
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking {uuid} not found",
        )
    return _serialize_public_booking(booking)


def _is_app_guest_booking_email(email: str | None) -> bool:
    normalized = (email or "").strip().lower()
    return normalized.startswith("guest.") and normalized.endswith("@taxibarcelona24.guest")


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _location_label(location: dict[str, Any] | None) -> str:
    if not location:
        return "—"
    label = location.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    address = location.get("address")
    if isinstance(address, str) and address.strip():
        return address.strip()
    return "—"


def _format_scheduled_time(iso: str | datetime) -> str:
    date = iso if isinstance(iso, datetime) else datetime.fromisoformat(iso.replace("Z", "+00:00"))
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


def _booking_customer_email(booking: dict[str, Any]) -> str | None:
    return (
        (booking.get("customerEmail") or "").strip().lower()
        or ((booking.get("user") or {}).get("email") or "").strip().lower()
        or None
    )


def _build_detail_row(label: str, value: str) -> str:
    return f"<li><strong>{_escape_html(label)}:</strong> {_escape_html(value)}</li>"


def _build_booking_details_html(booking: dict[str, Any]) -> str:
    user = booking.get("user") or {}
    customer_name = (booking.get("customerName") or user.get("fullName") or "—").strip()
    customer_email = _booking_customer_email(booking) or "—"
    customer_phone = (booking.get("customerPhone") or user.get("phone") or "—").strip()
    pickup = _location_label(booking.get("pickupLocation"))
    dropoff = _location_label(booking.get("dropoffLocation"))
    scheduled = _format_scheduled_time(booking["scheduledTime"])
    return_time = booking.get("returnTime")
    child_seats = _format_child_seats_summary(booking)
    flight = (booking.get("flightNumber") or "").strip() or None
    note = (booking.get("note") or "").strip() or None
    driver = ((booking.get("driver") or {}).get("name") or "").strip() or None

    rows = [
        _build_detail_row("Reference", booking["bookingReference"]),
        _build_detail_row("Passenger", customer_name),
        _build_detail_row("Email", customer_email),
        _build_detail_row("Phone", customer_phone),
        _build_detail_row("Pickup", pickup),
        _build_detail_row("Drop-off", dropoff),
        _build_detail_row("Pickup date & time", scheduled),
    ]
    if return_time:
        rows.append(_build_detail_row("Return date & time", _format_scheduled_time(return_time)))
    rows.append(_build_detail_row("Passengers", str(booking["passengerCount"])))
    if is_website_booking_public(booking):
        rows.append(_build_detail_row("Luggage pieces", str(booking["luggageCount"])))
        if child_seats:
            rows.append(_build_detail_row("Child seats", child_seats))
    if flight:
        rows.append(_build_detail_row("Flight number", flight))
    if note:
        rows.append(_build_detail_row("Notes", note))
    if driver:
        rows.append(_build_detail_row("Driver", driver))
    rows.append(_build_detail_row("Total fare", _format_fare_eur(booking["price"])))
    rows.append(_build_detail_row("Status", booking["status"]))
    return f"<ul>{''.join(rows)}</ul>"


class MailService:
    def is_enabled(self) -> bool:
        return is_smtp_configured()

    def _smtp_log_context(self) -> str:
        smtp = get_smtp_config()
        if not smtp:
            return "smtp=not-configured"
        return f"from={smtp.user} host={smtp.host}:{smtp.port} secure={smtp.secure}"

    def _send_html(self, smtp: SmtpConfig, to: str, subject: str, html: str) -> None:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{smtp.from_name} <{smtp.user}>"
        message["To"] = to
        message.attach(MIMEText(html, "html", "utf-8"))

        if smtp.secure and smtp.port == 465:
            server = smtplib.SMTP_SSL(smtp.host, smtp.port, timeout=30)
        else:
            server = smtplib.SMTP(smtp.host, smtp.port, timeout=30)
            if smtp.secure:
                server.starttls()
        try:
            server.login(smtp.user, smtp.password)
            server.sendmail(smtp.user, [to], message.as_string())
        finally:
            server.quit()

    async def send_booking_confirmation(
        self,
        to: str,
        booking: dict[str, Any] | None = None,
    ) -> bool:
        recipient = to.strip().lower()
        if _is_app_guest_booking_email(recipient):
            logger.info("Skipping booking confirmation for app guest email: to=%s", recipient)
            return False

        smtp = get_smtp_config()
        if not smtp:
            logger.warning("SMTP not configured — skipping booking confirmation email")
            return False

        reference = (booking or {}).get("bookingReference") or "your booking"
        details = _build_booking_details_html(booking) if booking else ""
        logger.info(
            "Sending booking confirmation: reference=%s to=%s %s",
            reference,
            recipient,
            self._smtp_log_context(),
        )
        try:
            await self._send_async(
                smtp,
                recipient,
                f"Booking confirmed — {reference}",
                f"""
                  <h1>Booking confirmed</h1>
                  <p>Thank you. Your taxi booking ({_escape_html(reference)}) was received successfully.</p>
                  {f"<h2>Booking details</h2>{details}" if details else ""}
                  <p>We will contact you if anything changes.</p>
                """,
            )
            return True
        except Exception:
            logger.exception(
                "Failed to send booking confirmation: reference=%s to=%s (%s)",
                reference,
                recipient,
                self._smtp_log_context(),
            )
            return False

    async def send_new_booking_alert(self, booking: dict[str, Any]) -> bool:
        notify_to = get_booking_notify_email()
        if not notify_to:
            logger.warning(
                "BOOKING_NOTIFY_EMAIL / SMTP_USER not set — skipping owner new-booking alert"
            )
            return False

        smtp = get_smtp_config()
        if not smtp:
            logger.warning("SMTP not configured — skipping owner new-booking alert")
            return False

        reference = booking["bookingReference"]
        heading = f"New Booking - {reference}"
        details = _build_booking_details_html(booking)
        try:
            await self._send_async(
                smtp,
                notify_to,
                heading,
                f"""
                  <h1>{_escape_html(heading)}</h1>
                  <p>A new taxi booking has been received. Customer and trip details are below.</p>
                  <h2>Booking details</h2>
                  {details}
                """,
            )
            return True
        except Exception:
            logger.exception(
                "Failed to send new-booking alert: reference=%s to=%s (%s)",
                reference,
                notify_to,
                self._smtp_log_context(),
            )
            return False

    async def send_booking_emails(self, booking: dict[str, Any]) -> dict[str, bool]:
        customer_email = _booking_customer_email(booking)
        if _is_app_guest_booking_email(customer_email):
            logger.info(
                "Skipping booking emails for app reservation: reference=%s",
                booking["bookingReference"],
            )
            return {"customerEmailSent": False, "ownerEmailSent": False}

        customer_sent = (
            await self.send_booking_confirmation(customer_email, booking)
            if customer_email
            else False
        )
        owner_sent = await self.send_new_booking_alert(booking)
        return {"customerEmailSent": customer_sent, "ownerEmailSent": owner_sent}

    async def send_test_email(self, to: str) -> dict[str, list[str]]:
        smtp = get_smtp_config()
        if not smtp:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMTP is not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASS in .env",
            )

        recipient = to.strip().lower()
        notify_to = get_booking_notify_email()
        recipients = list(dict.fromkeys([addr for addr in [recipient, notify_to] if addr]))
        sent_to: list[str] = []
        failures: list[str] = []

        for address in recipients:
            try:
                await self._send_async(
                    smtp,
                    address,
                    "SMTP test — taxi booking API",
                    f"<p>SMTP from <strong>{smtp.user}</strong> is working.</p>",
                )
                sent_to.append(address)
            except Exception:
                logger.exception("Failed to send SMTP test email to %s", address)
                failures.append(address)

        if not sent_to:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"SMTP test failed for all recipients: {', '.join(recipients)}",
            )
        return {"sentTo": sent_to}

    async def _send_async(
        self,
        smtp: SmtpConfig,
        to: str,
        subject: str,
        html: str,
    ) -> None:
        import asyncio

        await asyncio.to_thread(self._send_html, smtp, to, subject, html)


mail_service = MailService()
