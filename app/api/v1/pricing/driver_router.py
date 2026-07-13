from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_jwt
from app.db.session import get_session
from app.modules.auth.types import AuthenticatedUser
from app.modules.pricing.passcode_attempts import MAX_FAILED_ATTEMPTS
from app.modules.pricing.passcode_service import (
    pricing_unlock_status,
    require_pricing_unlocked,
    unlock_with_passcode,
)
from app.modules.pricing.schemas import PricingSettingsValues, PricingUnlockBody
from app.modules.pricing.service import pricing_admin_service

router = APIRouter(prefix="/drivers/me/pricing", tags=["driver-pricing"])


def _principal_id(user: AuthenticatedUser) -> str:
    return str(user.get("sub") or user.get("id") or "")


def _public_status(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "locked": bool(raw.get("locked")),
        "failures": int(raw.get("failures") or 0),
        "lockouts": int(raw.get("lockouts") or 0),
        "remainingSeconds": int(raw.get("remaining_seconds") or 0),
        "unlocked": bool(raw.get("unlocked")),
        "attemptsRemaining": int(
            raw.get("attempts_remaining")
            if raw.get("attempts_remaining") is not None
            else MAX_FAILED_ATTEMPTS
        ),
        "unlockedForSeconds": int(raw.get("unlocked_for_seconds") or 0),
    }


@router.get("/unlock-status")
async def unlock_status(
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    fresh: bool = False,
) -> dict[str, Any]:
    # fresh=true when opening the gate (back + re-enter): reset streak unless locked.
    return _public_status(pricing_unlock_status(_principal_id(user), fresh=fresh))


@router.post("/unlock")
async def unlock_pricing(
    body: PricingUnlockBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
) -> dict[str, Any]:
    result = unlock_with_passcode(session, _principal_id(user), body.code)
    # Wrong code must be 403 (not 401) so the app does not clear the driver session.
    if not result.get("unlocked"):
        remaining = int(result.get("attempts_remaining") or 0)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect passcode."
            if remaining > 0
            else "Incorrect passcode. No attempts left.",
        )
    return _public_status(result)


@router.get("")
async def get_pricing(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
) -> dict[str, Any]:
    require_pricing_unlocked(_principal_id(user))
    return pricing_admin_service.get(session)


@router.put("")
async def put_pricing(
    body: PricingSettingsValues,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
) -> dict[str, Any]:
    require_pricing_unlocked(_principal_id(user))
    return pricing_admin_service.update(session, body)
