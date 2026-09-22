from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_staff_admin
from app.core.rate_limit import MAIL_RATE_LIMIT, check_rate_limit, client_ip
from app.db.session import get_session
from app.lib.mail_config import get_booking_notify_email, get_smtp_config, get_smtp_port_warning, is_smtp_configured
from app.modules.auth.types import AuthenticatedUser
from app.modules.mail.schemas import (
    ContactInquiryBody,
    ResendBookingEmailsBody,
    SendBookingEmailBody,
    SendTestEmailBody,
)
from app.modules.mail.service import find_one_public_by_uuid, mail_service

router = APIRouter(prefix="/mail", tags=["mail"])


def _enforce_mail_rate_limit(request: Request) -> None:
    check_rate_limit(f"mail:{client_ip(request)}", limit=MAIL_RATE_LIMIT)


@router.post("/inquiry")
async def contact_inquiry(request: Request, body: ContactInquiryBody) -> dict:
    """Public website contact form — emails BOOKING_NOTIFY_EMAIL / SMTP inbox."""
    _enforce_mail_rate_limit(request)
    await mail_service.send_contact_inquiry(
        name=body.name,
        message=body.message,
        email=str(body.email) if body.email else None,
        phone=body.phone,
        booking_reference=body.booking_reference,
    )
    return {"success": True, "message": "Your message was sent."}


@router.post("/booking/confirm")
async def confirm_booking(
    request: Request,
    body: SendBookingEmailBody,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    _enforce_mail_rate_limit(request)
    booking = None
    if body.booking_uuid:
        booking = find_one_public_by_uuid(session, body.booking_uuid)
    email_sent = await mail_service.send_booking_confirmation(body.email, booking)
    if not mail_service.is_enabled() and not email_sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email is not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASS.",
        )
    return {"success": True, "emailSent": email_sent}


@router.get("/status")
async def get_status(
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
) -> dict:
    smtp = get_smtp_config()
    return {
        "smtpConfigured": is_smtp_configured(),
        "mailerReady": mail_service.is_enabled(),
        "smtpHost": smtp.host if smtp else None,
        "smtpPort": smtp.port if smtp else None,
        "smtpSecure": smtp.secure if smtp else None,
        "fromEmail": smtp.user if smtp else None,
        "bookingNotifyEmail": get_booking_notify_email(),
        "configWarning": get_smtp_port_warning(),
    }


@router.post("/test")
async def send_test(
    request: Request,
    body: SendTestEmailBody,
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
) -> dict:
    _enforce_mail_rate_limit(request)
    result = await mail_service.send_test_email(body.email)
    return {
        "success": True,
        "message": "Test email sent.",
        "sentTo": result["sentTo"],
        "bookingNotifyEmail": get_booking_notify_email(),
    }


@router.post("/booking/resend")
async def resend_booking_emails(
    request: Request,
    body: ResendBookingEmailsBody,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
) -> dict:
    _enforce_mail_rate_limit(request)
    if not mail_service.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email is not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASS.",
        )
    booking = find_one_public_by_uuid(session, body.booking_uuid)
    notifications = await mail_service.send_booking_emails(booking)
    return {
        "success": True,
        "bookingUuid": body.booking_uuid,
        "bookingReference": booking["bookingReference"],
        "bookingNotifyEmail": get_booking_notify_email(),
        **notifications,
    }
