from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_jwt
from app.db.session import get_session
from app.modules.auth.types import AuthenticatedUser
from app.modules.invoices.schemas import CreateDriverInvoiceBody, ListDriverInvoicesQuery
from app.modules.invoices.service import driver_invoices_service

router = APIRouter(prefix="/drivers/me/invoices", tags=["driver-invoices"])


@router.get("/suggested-price")
async def suggested_price(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    booking_reference: Annotated[str | None, Query(alias="bookingReference")] = None,
):
    ref = (booking_reference or "").strip()
    if not ref:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter bookingReference is required",
        )
    return driver_invoices_service.suggested_price_from_booking_reference(
        session,
        user,
        ref,
    )


@router.post("")
async def create(
    body: CreateDriverInvoiceBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return driver_invoices_service.create(session, user, body)


@router.get("")
async def find_all(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
):
    query = ListDriverInvoicesQuery(page=page, pageSize=page_size)
    return driver_invoices_service.find_all_paginated(session, user, query)


@router.get("/analytics")
async def analytics(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return driver_invoices_service.get_analytics(session, user)


@router.get("/{invoice_id}/pdf")
async def download_pdf(
    invoice_id: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    pdf_bytes = driver_invoices_service.build_pdf_buffer(session, user, invoice_id)
    filename = f"invoice-{invoice_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{invoice_id}")
async def find_one(
    invoice_id: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AuthenticatedUser, Depends(require_jwt)],
):
    return driver_invoices_service.find_one(session, user, invoice_id)
