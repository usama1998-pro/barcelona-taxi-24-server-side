"""
Quick IMAP diagnostic for #BR-TEST flow (no DB writes).
Usage: python -m scripts.debug_viator_inbox_test
"""

from __future__ import annotations

import email
import imaplib
import time
from datetime import datetime, timedelta

from app.lib.viator_inbox_config import get_hostinger_inbox_config
from app.lib.viator_test_email import (
    VIATOR_TEST_SUBJECT_MARKER,
    is_viator_test_booking_subject,
)
from scripts._bootstrap import bootstrap


def _header_fields(raw_fetch: bytes | tuple) -> tuple[str, str]:
    if isinstance(raw_fetch, tuple):
        payload = raw_fetch[1]
    else:
        payload = raw_fetch
    if not isinstance(payload, bytes):
        return "(no subject)", "?"
    message = email.message_from_bytes(payload)
    subject = message.get("Subject", "(no subject)")
    date = message.get("Date", "?")
    return str(subject), str(date)


def main() -> int:
    bootstrap()
    cfg = get_hostinger_inbox_config()
    if cfg is None:
        print("IMAP not configured (SMTP_USER / SMTP_PASS or IMAP_*).")
        return 1

    since = datetime.utcnow() - timedelta(days=1)
    since_text = since.strftime("%d-%b-%Y")
    started = time.time()

    client = imaplib.IMAP4_SSL(cfg.host, cfg.port)
    try:
        client.login(cfg.user, cfg.password)
        print(f"Connected to {cfg.host} as {cfg.user}")
        client.select(cfg.mailbox)

        search_new_started = time.time()
        status, data = client.search(
            None,
            "SINCE",
            since_text,
            "SUBJECT",
            '"New Booking for"',
        )
        uids_new = data[0].split() if status == "OK" and data[0] else []
        print(
            'SEARCH since+subject:"New Booking for" → '
            f"{len(uids_new)} uid(s) in {int((time.time() - search_new_started) * 1000)}ms"
        )

        search_marker_started = time.time()
        try:
            status_marker, data_marker = client.search(
                None,
                "SINCE",
                since_text,
                "SUBJECT",
                f'"{VIATOR_TEST_SUBJECT_MARKER}"',
            )
            uids_marker = (
                data_marker[0].split() if status_marker == "OK" and data_marker[0] else []
            )
            print(
                f'SEARCH since+subject:"{VIATOR_TEST_SUBJECT_MARKER}" → '
                f"{len(uids_marker)} uid(s) in "
                f"{int((time.time() - search_marker_started) * 1000)}ms"
            )
        except imaplib.IMAP4.error as error:
            print(
                f'SEARCH subject:"{VIATOR_TEST_SUBJECT_MARKER}" failed after '
                f"{int((time.time() - search_marker_started) * 1000)}ms: {error}"
            )

        if not uids_new:
            print("No candidates. Run: python -m scripts.send_viator_test_email")
            return 0

        test_count = 0
        for uid in uids_new[-20:]:
            status_fetch, fetched = client.fetch(
                uid,
                "(UID BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])",
            )
            if status_fetch != "OK" or not fetched:
                continue
            subject, date = _header_fields(fetched[0])
            is_test = is_viator_test_booking_subject(subject)
            if is_test:
                test_count += 1
            uid_text = uid.decode() if isinstance(uid, bytes) else str(uid)
            print(
                f"  uid={uid_text} date={date} test={is_test} "
                f"subject={subject[:100]}"
            )

        print(f"#BR-TEST matches in last 20 candidates: {test_count}")
    finally:
        try:
            client.logout()
        except imaplib.IMAP4.error:
            pass
        print(f"Done in {int((time.time() - started) * 1000)}ms")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
