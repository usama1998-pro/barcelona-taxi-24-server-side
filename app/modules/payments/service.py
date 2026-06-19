from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx
import stripe
from fastapi import HTTPException, status

from app.core.config import settings


@dataclass
class _PayPalTokenCache:
    access_token: str
    expires_at_ms: float


class PaymentsService:
    def __init__(self) -> None:
        self._paypal_token_cache: _PayPalTokenCache | None = None

    def _paypal_api_base(self) -> str:
        mode = settings.paypal_mode.strip().lower()
        if mode == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

    def _paypal_credentials(self) -> tuple[str, str]:
        client_id = (settings.paypal_client_id or "").strip()
        client_secret = (settings.paypal_client_secret or "").strip()
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "PayPal is not configured on the server "
                    "(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET)."
                ),
            )
        return client_id, client_secret

    async def _get_paypal_access_token(self) -> str:
        now = time.time() * 1000
        if (
            self._paypal_token_cache
            and self._paypal_token_cache.expires_at_ms > now + 60_000
        ):
            return self._paypal_token_cache.access_token

        client_id, client_secret = self._paypal_credentials()
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._paypal_api_base()}/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
            payload = response.json() if response.content else {}

        if response.status_code >= 400 or not payload.get("access_token"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=payload.get("error_description")
                or "Could not authenticate with PayPal.",
            )

        expires_in = payload.get("expires_in")
        expires_in_sec = expires_in if isinstance(expires_in, (int, float)) else 3600
        self._paypal_token_cache = _PayPalTokenCache(
            access_token=payload["access_token"],
            expires_at_ms=now + float(expires_in_sec) * 1000,
        )
        return payload["access_token"]

    async def _paypal_request(
        self,
        path: str,
        *,
        method: str = "GET",
        json_body: dict | None = None,
    ) -> dict:
        access_token = await self._get_paypal_access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                f"{self._paypal_api_base()}{path}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=json_body,
            )
            payload = response.json() if response.content else {}

        if response.status_code >= 400:
            details = payload.get("details") or []
            detail = details[0].get("description") if details else None
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail or payload.get("message") or "PayPal request failed.",
            )
        return payload

    async def create_paypal_order(
        self,
        amount_eur: float,
        description: str | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict[str, str]:
        amount_cents = round(amount_eur * 100)
        if amount_cents < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount is too small.",
            )

        trimmed_return = (return_url or "").strip()
        trimmed_cancel = (cancel_url or "").strip()
        paypal_locale = (os.getenv("PAYPAL_LOCALE") or "en-US").strip() or "en-US"
        application_context = None
        if trimmed_return and trimmed_cancel:
            application_context = {
                "return_url": trimmed_return,
                "cancel_url": trimmed_cancel,
                "user_action": "PAY_NOW",
                "shipping_preference": "NO_SHIPPING",
                "locale": paypal_locale,
            }

        body: dict = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": "EUR",
                        "value": f"{amount_eur:.2f}",
                    },
                }
            ],
        }
        if description and description.strip():
            body["purchase_units"][0]["description"] = description.strip()
        if application_context:
            body["application_context"] = application_context

        order = await self._paypal_request("/v2/checkout/orders", method="POST", json_body=body)
        order_id = order.get("id")
        if not order_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PayPal did not return an order id for this payment.",
            )
        return {"orderId": order_id}

    async def capture_paypal_order(self, order_id: str) -> dict[str, str]:
        trimmed_id = order_id.strip()
        if not trimmed_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PayPal order id is required.",
            )

        capture = await self._paypal_request(
            f"/v2/checkout/orders/{quote(trimmed_id, safe='')}/capture",
            method="POST",
        )
        capture_status = capture.get("status") or ""
        if capture_status != "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PayPal payment was not completed.",
            )
        return {"status": capture_status}

    def _stripe_secret_key(self) -> str:
        key = (settings.stripe_secret_key or "").strip()
        if not key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Card payments are not configured on the server (STRIPE_SECRET_KEY).",
            )
        return key

    async def create_stripe_payment_intent(self, amount_eur: float) -> dict[str, str]:
        amount_cents = round(amount_eur * 100)
        if amount_cents < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount is too small.",
            )

        stripe.api_key = self._stripe_secret_key()
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="eur",
            automatic_payment_methods={"enabled": True},
        )
        client_secret = intent.client_secret
        if not client_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe did not return a client secret for this payment.",
            )
        return {"clientSecret": client_secret}


payments_service = PaymentsService()
