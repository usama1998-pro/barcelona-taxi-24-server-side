from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_staff_admin
from app.db.session import get_session
from app.modules.auth.types import AuthenticatedUser
from app.modules.pricing.schemas import PricingSettingsValues
from app.modules.pricing.service import pricing_admin_service

router = APIRouter(prefix="/admin/pricing", tags=["admin"])


@router.get("")
async def get_pricing(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
) -> dict[str, Any]:
    return pricing_admin_service.get(session)


@router.put("")
async def put_pricing(
    body: PricingSettingsValues,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
) -> dict[str, Any]:
    return pricing_admin_service.update(session, body)
