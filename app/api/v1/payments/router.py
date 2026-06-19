from typing import Annotated

from fastapi import APIRouter, Depends

from app.modules.payments.schemas import (
    CapturePayPalOrderBody,
    CreatePayPalOrderBody,
    CreateStripeIntentBody,
)
from app.modules.payments.service import payments_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/stripe/intent")
async def create_stripe_intent(body: CreateStripeIntentBody) -> dict[str, str]:
    return await payments_service.create_stripe_payment_intent(body.amount_eur)


@router.post("/paypal/order")
async def create_paypal_order(body: CreatePayPalOrderBody) -> dict[str, str]:
    return await payments_service.create_paypal_order(
        body.amount_eur,
        body.description,
        body.return_url,
        body.cancel_url,
    )


@router.post("/paypal/capture")
async def capture_paypal_order(body: CapturePayPalOrderBody) -> dict[str, str]:
    return await payments_service.capture_paypal_order(body.order_id)
