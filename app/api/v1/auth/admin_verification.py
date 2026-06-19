from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_jwt
from app.db.session import get_session
from app.modules.auth.driver_verification_admin import driver_verification_admin_service
from app.modules.auth.schemas import (
    SetVerificationActiveBody,
    SetVerificationCodeBody,
    UpdateVerificationCodeBody,
)
from app.modules.auth.types import AuthenticatedUser

router = APIRouter(
    prefix="/admin/driver-verification-codes",
    tags=["admin"],
)


@router.post("")
async def set_code(
    body: SetVerificationCodeBody,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return driver_verification_admin_service.set_for_driver_email(
        session,
        driver_email=body.driver_email,
        code=body.code,
        is_active=body.is_active,
    )


@router.patch("/by-email")
async def patch_by_email(
    body: UpdateVerificationCodeBody,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return driver_verification_admin_service.update_for_driver_email(
        session,
        driver_email=body.driver_email,
        code=body.code,
        is_active=body.is_active,
    )


@router.patch("/{driver_id}")
async def patch_by_driver_id(
    driver_id: str,
    body: SetVerificationActiveBody,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return driver_verification_admin_service.set_active(
        session,
        driver_id,
        body.is_active,
    )


@router.delete("/by-email/{driver_email}")
async def remove_by_email(
    driver_email: str,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return driver_verification_admin_service.remove_by_driver_email(
        session,
        driver_email,
    )


@router.delete("/{driver_id}")
async def remove_by_driver_id(
    driver_id: str,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return driver_verification_admin_service.remove(session, driver_id)
