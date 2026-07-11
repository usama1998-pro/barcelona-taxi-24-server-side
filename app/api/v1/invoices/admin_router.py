from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_staff_admin
from app.db.session import get_session
from app.modules.auth.types import AuthenticatedUser
from app.modules.invoices.admin_service import admin_invoices_service
from app.modules.invoices.schemas import CreateDriverInvoiceBody

router = APIRouter(prefix="/admin/invoices", tags=["admin"])


@router.get("/suggested-price")
async def suggested_price(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
    booking_reference: Annotated[str | None, Query(alias="bookingReference")] = None,
):
    return admin_invoices_service.suggested_price_from_reference(
        session,
        booking_reference or "",
    )


@router.post("/pdf")
async def generate_pdf(
    body: CreateDriverInvoiceBody,
    _: Annotated[AuthenticatedUser, Depends(require_staff_admin)],
):
    pdf_bytes = admin_invoices_service.build_pdf(body)
    ref = body.booking_reference.strip() or "invoice"
    safe_ref = "".join(c for c in ref if c.isalnum() or c in ("-", "_")) or "invoice"
    filename = f"invoice-{safe_ref}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
