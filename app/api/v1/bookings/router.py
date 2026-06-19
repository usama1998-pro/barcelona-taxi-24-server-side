from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_jwt
from app.db.session import get_session
from app.modules.auth.types import AuthenticatedUser
from app.modules.bookings.schemas import (
    BookingTimeScope,
    CreateBookingBody,
    ListBookingsQuery,
    UpdateBookingBody,
)
from app.modules.bookings.service import bookings_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _list_query(
    page: Annotated[int | None, Query(ge=1)] = None,
    page_size: Annotated[int | None, Query(alias="pageSize", ge=1, le=100)] = None,
    time_scope: Annotated[BookingTimeScope | None, Query(alias="timeScope")] = None,
    scheduled_on: Annotated[str | None, Query(alias="scheduledOn")] = None,
    booking_reference: Annotated[str | None, Query(alias="bookingReference", max_length=64)] = None,
) -> ListBookingsQuery:
    return ListBookingsQuery(
        page=page or 1,
        pageSize=page_size or 20,
        timeScope=time_scope,
        scheduledOn=scheduled_on,
        bookingReference=booking_reference,
    )


@router.post("")
async def create(
    body: CreateBookingBody,
    session: Annotated[Session, Depends(get_session)],
):
    return bookings_service.create(session, body)


@router.get("")
async def find_all(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    query: Annotated[ListBookingsQuery, Depends(_list_query)],
):
    return bookings_service.find_all(session, user, query)


@router.get("/trash")
async def find_trash(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    query: Annotated[ListBookingsQuery, Depends(_list_query)],
):
    return bookings_service.find_trash(session, user, query)


@router.post("/trash/purge", status_code=status.HTTP_202_ACCEPTED)
async def purge_trash_batch():
    return bookings_service.enqueue_purge_trash_batch()


@router.post("/trash/clear")
async def clear_trash(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.clear_trash(session)


@router.get("/{uuid}")
async def find_one(
    uuid: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.find_one(session, uuid, user)


@router.patch("/{uuid}")
async def update(
    uuid: str,
    body: UpdateBookingBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.update(session, uuid, body, user)


@router.patch("/{uuid}/complete")
async def complete_reservation(
    uuid: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.complete_reservation(session, uuid, user)


@router.delete("/{uuid}")
async def remove(
    uuid: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.remove(session, uuid, user)


@router.delete("/{uuid}/remove")
async def remove_reservation(
    uuid: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.remove(session, uuid, user)
