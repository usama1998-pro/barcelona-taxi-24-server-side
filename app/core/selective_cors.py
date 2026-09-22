"""CORS that skips Access-Control headers for booking check/list GETs.

Admin UI (`/my-portal`) and native apps do not need CORS. The public website
still gets CORS for booking *create* (POST /api/v1/bookings) and other public
routes.
"""

from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send

from app.api.versioning import API_V1_PREFIX

_BOOKINGS_PREFIX = f"{API_V1_PREFIX}/bookings"


def is_booking_check_path(path: str, method: str) -> bool:
    """True for JWT booking list/detail reads — no CORS headers."""
    method_u = method.upper()
    if method_u not in {"GET", "HEAD", "OPTIONS"}:
        return False
    return path == _BOOKINGS_PREFIX or path.startswith(f"{_BOOKINGS_PREFIX}/")


class SelectiveCORSMiddleware(CORSMiddleware):
    """Same as CORSMiddleware, but booking check GETs get no CORS headers."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope.get("path") or ""
            method = scope.get("method") or "GET"
            if is_booking_check_path(path, method):
                await self.app(scope, receive, send)
                return
        await super().__call__(scope, receive, send)
