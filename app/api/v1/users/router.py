from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_users_resource
from app.db.session import get_session
from app.modules.auth.types import AuthenticatedUser
from app.modules.users.schemas import UpdateUserBody
from app.modules.users.service import users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def find_all(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_users_resource)],
):
    return users_service.find_all(session, user)


@router.get("/{id}")
async def find_one(
    id: str,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_users_resource)],
):
    return users_service.find_one(session, id)


@router.patch("/{id}")
async def update(
    id: str,
    body: UpdateUserBody,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_users_resource)],
):
    return users_service.update(session, id, body)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(
    id: str,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_users_resource)],
):
    users_service.remove(session, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
