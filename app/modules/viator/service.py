from __future__ import annotations

import asyncio
import email
import imaplib
import logging
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.utils.ids import new_id
from app.db.models.viator_alert import ViatorAlert
from app.lib.booking_reference import normalize_booking_reference
from app.lib.viator_allowed_products import is_allowed_viator_product_code
from app.lib.viator_inbox_config import get_hostinger_inbox_config, is_imap_configured
from app.lib.viator_test_email import (
    get_booking_time_zone,
    is_viator_test_booking_subject,
    is_viator_test_email_source,
    parse_viator_test_booking_subject,
)
from app.modules.viator.booking_fields import ViatorBookingDetails, merge_booking_fields
from app.modules.viator.bookings_port import (
    create_from_viator_sync,
    find_reserved_booking_by_reference,
    is_booking_reference_reserved,
)
from app.modules.viator.constants import VIATOR_INBOX_LOOKBACK_HOURS
from app.modules.viator.imap_session import select_mailbox, with_imap_session
from app.modules.viator.parse_email_body import (
    parse_viator_booking_reference_from_body,
    parse_viator_email_body,
)
from app.modules.viator.parse_scheduled_time import assert_pickup_not_in_past, parse_scheduled_time
from app.modules.viator.parse_subject import parse_viator_new_booking_subject
from app.modules.viator.to_booking_mapper import map_viator_to_create_booking_dto

logger = logging.getLogger(__name__)


class ViatorService:
    def __init__(self) -> None:
        self._inbox_check_running = False

    def _row_to_dto(self, row: ViatorAlert) -> dict[str, Any]:
        payload = dict(row.payload or {})
        is_test_booking = payload.pop("isTestBooking", None)
        dto: dict[str, Any] = {
            "id": row.id,
            "subject": row.subject,
            "viatorReference": row.viator_reference,
            "pickupDateLabel": row.pickup_date_label,
            "receivedAt": row.received_at.replace(tzinfo=timezone.utc).isoformat(),
            **payload,
        }
        if is_test_booking:
            dto["isTestBooking"] = True
        return dto

    def list_notifications(self, session: Session, limit: int | None = None) -> list[dict[str, Any]]:
        take = min(max(limit or 50, 1), 100)
        rows = session.scalars(
            select(ViatorAlert)
            .where(ViatorAlert.dismissed_at.is_(None))
            .order_by(ViatorAlert.received_at.desc())
            .limit(take)
        ).all()
        return [self._row_to_dto(row) for row in rows]

    def get_unread_count(self, session: Session) -> int:
        return session.scalar(
            select(func.count())
            .select_from(ViatorAlert)
            .where(ViatorAlert.dismissed_at.is_(None))
        ) or 0

    def dismiss_notification(self, session: Session, notification_id: str) -> dict[str, Any]:
        row = session.get(ViatorAlert, notification_id)
        if not row or row.dismissed_at:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        row.dismissed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()
        session.refresh(row)
        return self._row_to_dto(row)

    def dismiss_all_notifications(self, session: Session) -> dict[str, int]:
        rows = session.scalars(
            select(ViatorAlert).where(ViatorAlert.dismissed_at.is_(None))
        ).all()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for row in rows:
            row.dismissed_at = now
        session.commit()
        return {"updated": len(rows)}

    def enqueue_inbox_check(self) -> dict[str, Any]:
        if not is_imap_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Hostinger mail not configured. Set IMAP_HOST, SMTP_USER, and SMTP_PASS "
                    "(same mailbox that receives Viator emails)."
                ),
            )
        if self._inbox_check_running:
            return {
                "accepted": False,
                "status": "already_running",
                "lookbackHours": VIATOR_INBOX_LOOKBACK_HOURS,
                "message": (
                    "An inbox check is already running. New bookings will appear via "
                    "GET /viator/notifications when it finishes."
                ),
            }

        self._inbox_check_running = True
        asyncio.create_task(self._run_inbox_check_in_background())
        return {
            "accepted": True,
            "status": "started",
            "lookbackHours": VIATOR_INBOX_LOOKBACK_HOURS,
            "message": (
                f"Inbox check started in the background (Viator + #BR-TEST, last "
                f"{VIATOR_INBOX_LOOKBACK_HOURS}h). Use GET /viator/notifications for alerts."
            ),
        }

    async def _run_inbox_check_in_background(self) -> None:
        try:
            await asyncio.to_thread(self._run_inbox_check_work)
        except Exception as error:
            logger.warning("Viator inbox check failed: %s", error)
        finally:
            self._inbox_check_running = False

    def _recent_inbox_cutoff(self) -> datetime:
        return datetime.now(timezone.utc) - timedelta(hours=VIATOR_INBOX_LOOKBACK_HOURS)

    def _parse_email_for_import(self, subject: str) -> dict[str, Any] | None:
        trimmed = subject.strip()
        test_parsed = parse_viator_test_booking_subject(trimmed)
        if test_parsed and is_viator_test_booking_subject(trimmed):
            return {
                "pickupDateLabel": test_parsed["pickupDateLabel"],
                "viatorReference": "",
                "isTestBooking": True,
            }
        parsed = parse_viator_new_booking_subject(trimmed)
        if not parsed:
            return None
        return {**parsed, "isTestBooking": False}

    def _bump_viator_scheduled_time_if_past(self, scheduled_time_iso: str) -> str:
        scheduled = parse_scheduled_time(scheduled_time_iso)
        now = datetime.now(timezone.utc)
        guard = 0
        while scheduled.timestamp() < now.timestamp() and guard < 400:
            scheduled = scheduled + timedelta(days=1)
            guard += 1
        return scheduled.isoformat()

    def _persist_viator_booking(
        self,
        session: Session,
        *,
        viator_reference: str,
        pickup_date_label: str,
        details: ViatorBookingDetails,
    ) -> dict[str, Any]:
        ref = normalize_booking_reference(viator_reference)
        try:
            reserved = find_reserved_booking_by_reference(session, ref)
            if reserved:
                return {
                    "viatorReference": ref,
                    "bookingUuid": reserved["uuid"],
                    "savedToDb": False,
                    "alreadyInDatabase": True,
                }

            dto = map_viator_to_create_booking_dto(
                {
                    "viatorReference": ref,
                    "pickupDateLabel": pickup_date_label,
                    "details": details,
                }
            )
            dto["scheduledTime"] = self._bump_viator_scheduled_time_if_past(dto["scheduledTime"])
            assert_pickup_not_in_past(parse_scheduled_time(dto["scheduledTime"]))
            booking, created = create_from_viator_sync(session, dto)
            return {
                "viatorReference": ref,
                "bookingUuid": booking["uuid"],
                "savedToDb": created,
                "alreadyInDatabase": not created,
            }
        except HTTPException as error:
            message = str(error.detail)
            logger.warning("Could not save Viator booking %s: %s", ref, message)
            return {
                "viatorReference": ref,
                "savedToDb": False,
                "alreadyInDatabase": False,
                "error": message,
            }
        except Exception as error:
            message = str(error)
            logger.warning("Could not save Viator booking %s: %s", ref, message)
            return {
                "viatorReference": ref,
                "savedToDb": False,
                "alreadyInDatabase": False,
                "error": message,
            }

    def _is_duplicate_test_imap_uid(self, session: Session, imap_uid: int) -> bool:
        rows = session.scalars(select(ViatorAlert)).all()
        return any((row.payload or {}).get("imapUid") == imap_uid for row in rows)

    def _create_alert_for_new_booking(
        self,
        session: Session,
        entry: dict[str, Any],
        booking_uuid: str | None = None,
    ) -> dict[str, Any] | None:
        existing = session.scalar(
            select(ViatorAlert).where(
                ViatorAlert.viator_reference == entry["viatorReference"]
            )
        )
        if existing:
            return None

        booking_fields = merge_booking_fields(
            {key: value for key, value in entry.items() if isinstance(value, str)}
        )
        payload = dict(booking_fields)
        if entry.get("isTestBooking"):
            payload["isTestBooking"] = True
        payload["imapUid"] = entry.get("imapUid")

        row = ViatorAlert(
            id=entry["id"],
            viator_reference=entry["viatorReference"],
            subject=entry["subject"],
            pickup_date_label=entry["pickupDateLabel"],
            received_at=datetime.fromisoformat(entry["receivedAt"].replace("Z", "+00:00")).replace(
                tzinfo=None
            ),
            booking_uuid=booking_uuid,
            payload=payload,
            dismissed_at=None,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return self._row_to_dto(row)

    def _decode_subject(self, subject: str | None) -> str:
        if not subject:
            return ""
        try:
            return str(make_header(decode_header(subject)))
        except Exception:
            return subject

    def _fetch_message_row(
        self,
        client: imaplib.IMAP4_SSL,
        uid: int,
    ) -> dict[str, Any] | None:
        status_code, data = client.uid("fetch", str(uid), "(RFC822)")
        if status_code != "OK" or not data or not data[0]:
            return None
        part = data[0]
        if not isinstance(part, tuple) or not isinstance(part[1], bytes):
            return None
        message = email.message_from_bytes(part[1])
        subject = self._decode_subject(message.get("Subject"))
        received_at = datetime.now(timezone.utc)
        date_header = message.get("Date")
        if date_header:
            try:
                received_at = email.utils.parsedate_to_datetime(date_header)
                if received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=timezone.utc)
            except Exception:
                pass
        return {
            "uid": uid,
            "subject": subject,
            "receivedAt": received_at,
            "source": part[1],
        }

    def _run_inbox_check_work(self) -> None:
        from app.db.session import _session_factory

        cfg = get_hostinger_inbox_config()
        if not cfg:
            return

        cutoff = self._recent_inbox_cutoff()
        logger.info(
            "Viator inbox check started (lookback=%sh, since=%s, tz=%s)",
            VIATOR_INBOX_LOOKBACK_HOURS,
            cutoff.isoformat(),
            get_booking_time_zone(),
        )

        def sync_inbox(client: imaplib.IMAP4_SSL) -> None:
            select_mailbox(client, cfg.mailbox)
            since = cutoff.strftime("%d-%b-%Y")
            status_code, data = client.uid(
                "search",
                None,
                f'(SINCE {since} SUBJECT "New Booking for")',
            )
            if status_code != "OK":
                logger.warning("IMAP search failed: %s", status_code)
                return

            uids = [int(item) for item in (data[0] or b"").split() if item.isdigit()]
            logger.info("Inbox check IMAP search returned %s candidate message(s)", len(uids))
            rows: list[dict[str, Any]] = []
            for uid in uids:
                row = self._fetch_message_row(client, uid)
                if row and row["receivedAt"] >= cutoff:
                    rows.append(row)
            rows.sort(key=lambda item: item["receivedAt"], reverse=True)

            processed_refs: set[str] = set()
            for row in rows:
                parsed = self._parse_email_for_import(row["subject"])
                if not parsed:
                    continue
                if not parsed.get("isTestBooking") and is_viator_test_email_source(
                    row["source"]
                ):
                    parsed["isTestBooking"] = True
                    parsed["viatorReference"] = ""

                session = _session_factory()()
                try:
                    if not parsed.get("isTestBooking"):
                        if parsed["viatorReference"] in processed_refs:
                            continue
                        if is_booking_reference_reserved(session, parsed["viatorReference"]):
                            continue
                    elif self._is_duplicate_test_imap_uid(session, row["uid"]):
                        continue

                    viator_reference = parsed["viatorReference"]
                    source = row["source"]
                    if parsed.get("isTestBooking"):
                        from_body = parse_viator_booking_reference_from_body(
                            source,
                            allow_test_marker=True,
                        )
                        if not from_body:
                            continue
                        viator_reference = from_body
                        parsed["viatorReference"] = from_body
                    else:
                        from_body = parse_viator_booking_reference_from_body(source)
                        if from_body:
                            viator_reference = from_body
                            parsed["viatorReference"] = from_body

                    details = parse_viator_email_body(source)
                    if not is_allowed_viator_product_code(details.get("productCode")):
                        continue

                    if parsed.get("isTestBooking") and self._is_duplicate_test_imap_uid(
                        session, row["uid"]
                    ):
                        continue
                    if not parsed.get("isTestBooking") and is_booking_reference_reserved(
                        session, viator_reference
                    ):
                        continue

                    persist = self._persist_viator_booking(
                        session,
                        viator_reference=viator_reference,
                        pickup_date_label=parsed["pickupDateLabel"],
                        details=details,
                    )
                    if persist.get("error") or (
                        not persist.get("savedToDb") and not persist.get("alreadyInDatabase")
                    ):
                        continue
                    if not persist.get("savedToDb") and persist.get("alreadyInDatabase"):
                        continue

                    entry = {
                        "id": new_id(),
                        "subject": row["subject"].strip(),
                        "viatorReference": viator_reference,
                        "pickupDateLabel": parsed["pickupDateLabel"],
                        "receivedAt": row["receivedAt"].astimezone(timezone.utc).isoformat(),
                        "imapUid": row["uid"],
                        "isTestBooking": parsed.get("isTestBooking"),
                        **merge_booking_fields(details),
                    }
                    dto = self._create_alert_for_new_booking(
                        session,
                        entry,
                        persist.get("bookingUuid"),
                    )
                    if dto and not parsed.get("isTestBooking"):
                        processed_refs.add(viator_reference)
                    if dto:
                        logger.info("New Viator booking: %s", viator_reference)
                finally:
                    session.close()

        with_imap_session(cfg, sync_inbox)

        session = _session_factory()()
        try:
            logger.info("Viator inbox check done (unread=%s)", self.get_unread_count(session))
        finally:
            session.close()


viator_service = ViatorService()
