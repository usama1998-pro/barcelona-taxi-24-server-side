from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_jwt
from app.api.v1.bookings.error_handling import handle_booking_errors
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
@handle_booking_errors("create")
async def create(
    body: CreateBookingBody,
    session: Annotated[Session, Depends(get_session)],
):
    return bookings_service.create(session, body)


@router.get("")
@handle_booking_errors("find_all")
async def find_all(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    query: Annotated[ListBookingsQuery, Depends(_list_query)],
):
    return bookings_service.find_all(session, user, query)


@router.get("/trash")
@handle_booking_errors("find_trash")
async def find_trash(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    query: Annotated[ListBookingsQuery, Depends(_list_query)],
):
    return bookings_service.find_trash(session, user, query)


@router.post("/trash/purge", status_code=status.HTTP_202_ACCEPTED)
@handle_booking_errors("purge_trash_batch")
async def purge_trash_batch():
    return bookings_service.enqueue_purge_trash_batch()


@router.post("/trash/clear")
@handle_booking_errors("clear_trash")
async def clear_trash(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.clear_trash(session)


@router.get("/{uuid}")
@handle_booking_errors("find_one")
async def find_one(
    uuid: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.find_one(session, uuid, user)


@router.patch("/{uuid}")
@handle_booking_errors("update")
async def update(
    uuid: str,
    body: UpdateBookingBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.update(session, uuid, body, user)


@router.patch("/{uuid}/complete")
@handle_booking_errors("complete_reservation")
async def complete_reservation(
    uuid: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.complete_reservation(session, uuid, user)


@router.delete("/{uuid}")
@handle_booking_errors("remove")
async def remove(
    uuid: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.remove(session, uuid, user)


@router.delete("/{uuid}/remove")
@handle_booking_errors("remove_reservation")
async def remove_reservation(
    uuid: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return bookings_service.remove(session, uuid, user)
