from __future__ import annotations

from pydantic import BaseModel, Field


class CreateStripeIntentBody(BaseModel):
    amount_eur: float = Field(alias="amountEur", ge=0.5)

    model_config = {"populate_by_name": True}


class CreatePayPalOrderBody(BaseModel):
    amount_eur: float = Field(alias="amountEur", ge=0.5)
    description: str | None = None
    return_url: str | None = Field(default=None, alias="returnUrl")
    cancel_url: str | None = Field(default=None, alias="cancelUrl")

    model_config = {"populate_by_name": True}


class CapturePayPalOrderBody(BaseModel):
    order_id: str = Field(alias="orderId", min_length=1)

    model_config = {"populate_by_name": True}
