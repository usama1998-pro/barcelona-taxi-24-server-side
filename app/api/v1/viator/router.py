from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_jwt
from app.db.session import get_session
from app.modules.auth.types import AuthenticatedUser
from app.modules.viator.service import viator_service

router = APIRouter(prefix="/viator", tags=["viator"])


@router.post("/inbox/check", status_code=status.HTTP_202_ACCEPTED)
async def check_inbox() -> dict:
    return viator_service.enqueue_inbox_check()


@router.get("/notifications")
async def list_notifications(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
    limit: Annotated[int | None, Query()] = None,
) -> list[dict]:
    return viator_service.list_notifications(session, limit=limit)


@router.get("/notifications/unread-count")
async def unread_count(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
) -> dict[str, int]:
    return {"count": viator_service.get_unread_count(session)}


@router.patch("/notifications/read-all")
async def mark_all_read(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
) -> dict[str, int]:
    return viator_service.dismiss_all_notifications(session)


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
) -> dict:
    return viator_service.dismiss_notification(session, notification_id)
