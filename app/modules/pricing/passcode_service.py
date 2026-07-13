from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.pricing_passcode import PRICING_PASSCODE_ROW_ID, PricingPasscode
from app.modules.pricing.passcode_attempts import pricing_passcode_attempts


def get_stored_passcode(session: Session) -> str | None:
    row = session.get(PricingPasscode, PRICING_PASSCODE_ROW_ID)
    if row is None:
        return None
    code = (row.code or "").strip()
    return code or None


def set_stored_passcode(session: Session, code: str) -> None:
    now = datetime.now(timezone.utc)
    row = session.get(PricingPasscode, PRICING_PASSCODE_ROW_ID)
    if row is None:
        session.add(
            PricingPasscode(
                id=PRICING_PASSCODE_ROW_ID,
                code=code,
                updated_at=now,
            )
        )
    else:
        row.code = code
        row.updated_at = now
    session.commit()


def unlock_with_passcode(session: Session, principal_id: str, code: str) -> dict:
    pricing_passcode_attempts.assert_not_locked(principal_id)
    expected = get_stored_passcode(session)
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pricing passcode is not configured. Run: python -m scripts.set_pricing_passcode",
        )
    submitted = "".join(ch for ch in (code or "") if ch.isdigit())
    if submitted != expected:
        return pricing_passcode_attempts.record_failure(principal_id)
    return pricing_passcode_attempts.mark_unlocked(principal_id)


def require_pricing_unlocked(principal_id: str) -> None:
    pricing_passcode_attempts.assert_unlocked(principal_id)


def pricing_unlock_status(principal_id: str, *, fresh: bool = False) -> dict:
    if fresh:
        return pricing_passcode_attempts.begin_gate_visit(principal_id)
    return pricing_passcode_attempts.status(principal_id)
