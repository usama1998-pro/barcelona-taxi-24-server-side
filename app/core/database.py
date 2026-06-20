import asyncio
import ssl
from typing import Any

from fastapi import FastAPI, Request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import Settings, settings


def database_connect_args(config: Settings = settings) -> dict[str, Any]:
    args: dict[str, Any] = {}

    if config.database_connect_timeout_ms is not None:
        args["connect_timeout"] = config.database_connect_timeout_ms / 1000

    if config.database_ssl:
        ctx = ssl.create_default_context()
        if not config.database_ssl_reject_unauthorized:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        args["ssl"] = ctx

    return args


def create_db_engine(config: Settings = settings) -> Engine:
    return create_engine(
        config.database_url(),
        pool_pre_ping=True,
        pool_size=config.database_pool_connection_limit,
        max_overflow=0,
        connect_args=database_connect_args(config),
    )


async def ping_database(engine: Engine) -> None:
    def _ping() -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    await asyncio.to_thread(_ping)


def get_request_db_engine(request: Request) -> Engine:
    """
    Return the app pool engine. Under Passenger/WSGI, FastAPI lifespan may not
    run, so create the pool on first use and cache it on app.state.
    """
    app = request.app
    engine = getattr(app.state, "db_engine", None)
    if engine is not None:
        return engine
    engine = create_db_engine()
    app.state.db_engine = engine
    return engine


def ensure_app_db_engine(app: FastAPI) -> Engine:
    """Eager init for WSGI entrypoints (e.g. passenger_wsgi.py)."""
    engine = getattr(app.state, "db_engine", None)
    if engine is not None:
        return engine
    engine = create_db_engine()
    app.state.db_engine = engine
    return engine
