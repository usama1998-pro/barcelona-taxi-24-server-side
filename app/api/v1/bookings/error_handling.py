from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def _log_server_error(operation: str, detail: str) -> None:
    logger.error("Bookings %s: %s", operation, detail)


def handle_booking_errors(operation: str) -> Callable[[F], F]:
    """Log booking route failures and return the actual error for 500 responses."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException as exc:
                if exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
                    _log_server_error(operation, str(exc.detail))
                raise
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                logger.exception("Bookings %s failed: %s", operation, message)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=message,
                ) from exc

        return wrapper  # type: ignore[return-value]

    return decorator
