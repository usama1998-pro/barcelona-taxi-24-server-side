"""Throttle staff admin / portal endpoints (300 requests per minute per client)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.rate_limit import (
    ADMIN_RATE_LIMIT,
    check_rate_limit,
    client_ip,
    is_admin_throttle_path,
)
from fastapi import HTTPException


class AdminRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not is_admin_throttle_path(path):
            return await call_next(request)

        key = f"admin:{client_ip(request)}"
        try:
            check_rate_limit(key, limit=ADMIN_RATE_LIMIT)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=dict(exc.headers or {}),
            )
        return await call_next(request)
