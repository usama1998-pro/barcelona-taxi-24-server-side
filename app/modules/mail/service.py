from __future__ import annotations

import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models.booking import Booking
from app.lib.mail_config import (
    SmtpConfig,
    get_booking_notify_email,
    get_smtp_config,
    is_smtp_configured,
)
from app.modules.bookings.serializers import to_public_booking
from app.modules.mail.templates import (
    booking_customer_email,
    render_client_booking_confirmation_html,
    render_owner_new_booking_html,
)

logger = logging.getLogger(__name__)


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


def _normalize_email(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if not normalized or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        return None
    return normalized


class MailService:
    def is_enabled(self) -> bool:
        return is_smtp_configured()

    def _smtp_log_context(self) -> str:
        smtp = get_smtp_config()
        if not smtp:
            return "smtp=not-configured"
        return f"from={smtp.user} host={smtp.host}:{smtp.port} secure={smtp.secure}"

    def _plain_text_from_html(self, html: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</td>", " | ", text, flags=re.IGNORECASE)
        text = re.sub(r"</tr>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _send_html(
        self,
        smtp: SmtpConfig,
        to: str,
        subject: str,
        html: str,
        *,
        reply_to: str | None = None,
    ) -> None:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = formataddr((smtp.from_name, smtp.user))
        message["To"] = to
        message["Message-ID"] = make_msgid(domain=smtp.user.split("@")[-1])
        if reply_to:
            message["Reply-To"] = reply_to
        plain = self._plain_text_from_html(html)
        message.attach(MIMEText(plain, "plain", "utf-8"))
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
        notify_to = get_booking_notify_email()
        html = render_client_booking_confirmation_html(booking)
        logger.info(
            "Sending booking confirmation: reference=%s to=%s reply_to=%s %s",
            reference,
            recipient,
            notify_to or "none",
            self._smtp_log_context(),
        )
        try:
            await self._send_async(
                smtp,
                recipient,
                f"Booking confirmed — {reference}",
                html,
                reply_to=notify_to,
            )
            logger.info(
                "Booking confirmation sent: reference=%s to=%s",
                reference,
                recipient,
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
        html = render_owner_new_booking_html(booking)
        try:
            await self._send_async(
                smtp,
                notify_to,
                f"New Booking - {reference}",
                html,
            )
            logger.info(
                "New-booking alert sent: reference=%s to=%s",
                reference,
                notify_to,
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

    async def send_booking_emails(
        self,
        booking: dict[str, Any],
        *,
        customer_email_override: str | None = None,
    ) -> dict[str, bool]:
        customer_email = booking_customer_email(
            booking,
            override=customer_email_override,
        )
        notify_to = get_booking_notify_email()
        if _is_app_guest_booking_email(customer_email):
            logger.info(
                "Skipping booking emails for app reservation: reference=%s",
                booking["bookingReference"],
            )
            return {"customerEmailSent": False, "ownerEmailSent": False}

        logger.info(
            "Sending booking emails: reference=%s customer=%s owner=%s",
            booking["bookingReference"],
            customer_email or "none",
            notify_to or "none",
        )
        if not customer_email:
            logger.warning(
                "No customer email for booking %s — skipping customer confirmation",
                booking["bookingReference"],
            )

        customer_sent = (
            await self.send_booking_confirmation(customer_email, booking)
            if customer_email
            else False
        )
        owner_sent = await self.send_new_booking_alert(booking)
        logger.info(
            "Booking emails finished: reference=%s customerEmailSent=%s ownerEmailSent=%s",
            booking["bookingReference"],
            customer_sent,
            owner_sent,
        )
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

    async def send_contact_inquiry(
        self,
        *,
        name: str,
        message: str,
        email: str | None = None,
        phone: str | None = None,
        booking_reference: str | None = None,
    ) -> bool:
        notify_to = get_booking_notify_email()
        if not notify_to:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inquiry email is not configured. Set BOOKING_NOTIFY_EMAIL or SMTP_USER.",
            )

        smtp = get_smtp_config()
        if not smtp:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email is not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASS.",
            )

        safe_name = _escape_html(name.strip())
        safe_message = _escape_html(message.strip()).replace("\n", "<br/>")
        safe_email = _normalize_email(email)
        safe_phone = (phone or "").strip()
        safe_ref = (booking_reference or "").strip()

        rows: list[str] = [f"<tr><td><strong>Name</strong></td><td>{safe_name}</td></tr>"]
        if safe_email:
            rows.append(
                f"<tr><td><strong>Email</strong></td><td>{_escape_html(safe_email)}</td></tr>"
            )
        if safe_phone:
            rows.append(
                f"<tr><td><strong>Phone / WhatsApp</strong></td>"
                f"<td>{_escape_html(safe_phone)}</td></tr>"
            )
        if safe_ref:
            rows.append(
                f"<tr><td><strong>Booking reference</strong></td>"
                f"<td>{_escape_html(safe_ref)}</td></tr>"
            )

        subject = (
            f"Website inquiry — {safe_ref}"
            if safe_ref
            else f"Website inquiry from {name.strip()}"
        )

        html = f"""
          <h1>New website inquiry</h1>
          <p>Someone submitted the contact form on the website.</p>
          <table cellpadding="6" cellspacing="0" style="border-collapse:collapse">
            {''.join(rows)}
          </table>
          <h2>Message</h2>
          <p>{safe_message}</p>
        """

        logger.info(
            "Sending contact inquiry: to=%s from_name=%s reply_to=%s %s",
            notify_to,
            name.strip(),
            safe_email or "none",
            self._smtp_log_context(),
        )
        try:
            await self._send_async(
                smtp,
                notify_to,
                subject,
                html,
                reply_to=safe_email,
            )
            logger.info("Contact inquiry sent: to=%s", notify_to)
            return True
        except Exception:
            logger.exception(
                "Failed to send contact inquiry: to=%s (%s)",
                notify_to,
                self._smtp_log_context(),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not send your message. Please try again shortly.",
            ) from None

    async def _send_async(
        self,
        smtp: SmtpConfig,
        to: str,
        subject: str,
        html: str,
        *,
        reply_to: str | None = None,
    ) -> None:
        import asyncio

        await asyncio.to_thread(
            self._send_html,
            smtp,
            to,
            subject,
            html,
            reply_to=reply_to,
        )


mail_service = MailService()
