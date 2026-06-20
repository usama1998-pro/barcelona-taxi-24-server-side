"""Trace why each IMAP candidate is skipped. Run: python -m scripts.trace_viator_inbox"""

from __future__ import annotations

import imaplib

from sqlalchemy import text

from app.lib.viator_allowed_products import is_allowed_viator_product_code
from app.modules.viator.bookings_port import is_booking_reference_reserved
from app.modules.viator.parse_email_body import (
    parse_viator_booking_reference_from_body,
    parse_viator_email_body,
)
from app.modules.viator.service import viator_service
from scripts._bootstrap import bootstrap, db_engine


def main() -> int:
    bootstrap()
    from app.db.session import _session_factory
    from app.lib.viator_inbox_config import get_hostinger_inbox_config

    cfg = get_hostinger_inbox_config()
    if not cfg:
        print("IMAP not configured")
        return 1

    cutoff = viator_service._recent_inbox_cutoff()
    since = cutoff.strftime("%d-%b-%Y")
    client = imaplib.IMAP4_SSL(cfg.host, cfg.port)
    try:
        client.login(cfg.user, cfg.password)
        client.select(cfg.mailbox)
        _, data = client.uid("search", None, f'(SINCE {since} SUBJECT "New Booking for")')
        uids = [int(x) for x in (data[0] or b"").split() if x.isdigit()]
        print(f"UID search: {len(uids)} since {since}, cutoff={cutoff.isoformat()}")

        rows = []
        for uid in uids:
            row = viator_service._fetch_message_row(client, uid)
            if row and row["receivedAt"] >= cutoff:
                rows.append(row)
        print(f"After date filter: {len(rows)}")
        rows.sort(key=lambda item: item["receivedAt"], reverse=True)

        for row in rows[:8]:
            subj = row["subject"]
            parsed = viator_service._parse_email_for_import(subj)
            print(f"\n--- UID {row['uid']} ---")
            print(f"subject: {subj[:100]}")
            if not parsed:
                print("SKIP: subject not parseable")
                continue

            session = _session_factory()()
            try:
                is_test = bool(parsed.get("isTestBooking"))
                if is_test:
                    dup = viator_service._is_duplicate_test_imap_uid(session, row["uid"])
                    if dup:
                        print("SKIP: duplicate test imap uid")
                        continue
                    ref = parse_viator_booking_reference_from_body(
                        row["source"], allow_test_marker=True
                    )
                    if not ref:
                        print("SKIP: no booking ref in body")
                        continue
                    parsed["viatorReference"] = ref
                else:
                    ref = parsed["viatorReference"]
                    if is_booking_reference_reserved(session, ref):
                        print(f"SKIP: booking ref {ref} already in DB")
                        continue

                try:
                    details = parse_viator_email_body(row["source"])
                except Exception as error:
                    print(f"SKIP: body parse error: {error}")
                    continue

                product = details.get("productCode")
                if not is_allowed_viator_product_code(product):
                    print(f"SKIP: product code not allowed: {product!r}")
                    continue

                persist = viator_service._persist_viator_booking(
                    session,
                    viator_reference=parsed["viatorReference"],
                    pickup_date_label=parsed["pickupDateLabel"],
                    details=details,
                )
                if persist.get("error"):
                    print(f"SKIP: persist error: {persist['error']}")
                    continue
                if not persist.get("savedToDb") and not persist.get("alreadyInDatabase"):
                    print("SKIP: persist failed (unknown)")
                    continue

                print(
                    f"WOULD IMPORT: ref={parsed['viatorReference']} product={product} "
                    f"saved={persist.get('savedToDb')}"
                )
            finally:
                session.close()
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
