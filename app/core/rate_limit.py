"""Simple in-memory sliding-window rate limiter (per key, per minute)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

# Admin / portal surfaces: 300 requests per rolling minute.
ADMIN_RATE_LIMIT = 300
ADMIN_RATE_WINDOW_SECONDS = 60.0

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def check_rate_limit(key: str, *, limit: int = ADMIN_RATE_LIMIT, window: float = ADMIN_RATE_WINDOW_SECONDS) -> None:
    """Raise 429 if `key` has exceeded `limit` hits within `window` seconds."""
    now = time.monotonic()
    cutoff = now - window
    with _lock:
        bucket = _hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: max {limit} requests per minute.",
                headers={"Retry-After": "60"},
            )
        bucket.append(now)


def is_admin_throttle_path(path: str) -> bool:
    """Paths throttled at the middleware layer (UI + `/api/v1/admin/*` + trash purge)."""
    if path == "/my-portal" or path.startswith("/my-portal/"):
        return True
    if path.startswith("/api/v1/admin"):
        return True
    # Unauthenticated destructive endpoint — same 300/min cap as admin surfaces.
    if path == "/api/v1/bookings/trash/purge":
        return True
    return False
