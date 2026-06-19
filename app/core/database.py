import asyncio
import ssl
from typing import Any

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
