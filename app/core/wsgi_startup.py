"""Eager init for Passenger/WSGI workers where FastAPI lifespan may not run."""

from __future__ import annotations

from fastapi import FastAPI

from app.core.database import ensure_app_db_engine
from app.core.logging_setup import setup_logging

_wsgi_initialized = False


def ensure_wsgi_startup(app: FastAPI | None = None) -> None:
    """Configure logging (and optional DB pool) once per worker process."""
    global _wsgi_initialized
    if _wsgi_initialized:
        return
    setup_logging()
    if app is not None:
        ensure_app_db_engine(app)
    _wsgi_initialized = True
