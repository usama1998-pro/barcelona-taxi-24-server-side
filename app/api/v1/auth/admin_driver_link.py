from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_staff_admin
from app.db.session import get_session
from app.modules.auth.admin_driver_user_link import admin_driver_user_link_service
from app.modules.auth.schemas import AssignLinkedUserBody
from app.modules.auth.types import AuthenticatedUser

router = APIRouter(prefix="/admin/drivers", tags=["admin"])


@router.patch("/{driver_id}/linked-user")
async def assign_linked_user(
    driver_id: str,
    body: AssignLinkedUserBody,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
):
    return admin_driver_user_link_service.assign_linked_user(
        session,
        driver_id,
        body.user_id,
    )


@router.delete("/{driver_id}/linked-user")
async def clear_linked_user(
    driver_id: str,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
):
    return admin_driver_user_link_service.clear_linked_user(session, driver_id)
