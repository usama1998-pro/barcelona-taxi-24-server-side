from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_driver_self, require_jwt, require_staff_admin
from app.db.session import get_session
from app.modules.auth.types import AuthenticatedUser
from app.modules.drivers.schemas import (
    CreateCarBody,
    CreateDriverBody,
    PatchMyAvailabilityBody,
    UpdateCarBody,
    UpdateDriverBody,
)
from app.modules.drivers.service import drivers_service

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.post("")
async def create(
    body: CreateDriverBody,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
):
    return drivers_service.create(session, body)


@router.get("")
async def find_all(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    return drivers_service.find_all(session, user)


@router.get("/me/profile")
async def get_my_profile(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    return drivers_service.get_my_profile(session, user)


@router.patch("/me/availability")
async def patch_my_availability(
    body: PatchMyAvailabilityBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    return drivers_service.patch_my_availability(session, user, body.is_available)


@router.get("/{driver_id}/car")
async def get_car(
    driver_id: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    return drivers_service.get_car(session, driver_id)


@router.post("/{driver_id}/car")
async def create_car(
    driver_id: str,
    body: CreateCarBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    return drivers_service.create_car(session, driver_id, body)


@router.patch("/{driver_id}/car")
async def update_car(
    driver_id: str,
    body: UpdateCarBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    return drivers_service.update_car(session, driver_id, body)


@router.delete("/{driver_id}/car", status_code=status.HTTP_204_NO_CONTENT)
async def remove_car(
    driver_id: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    drivers_service.remove_car(session, driver_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{driver_id}")
async def find_one(
    driver_id: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    return drivers_service.find_one(session, driver_id)


@router.patch("/{driver_id}")
async def update(
    driver_id: str,
    body: UpdateDriverBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    return drivers_service.update(session, driver_id, body)


@router.delete("/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(
    driver_id: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    _: Annotated[AuthenticatedUser | None, Depends(require_driver_self)],
):
    drivers_service.remove(session, driver_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
