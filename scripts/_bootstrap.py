from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

_LOCAL_API_HOSTS = {"localhost", "127.0.0.1"}


def bootstrap() -> None:
    root_str = str(ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")


@contextmanager
def db_engine() -> Iterator:
    bootstrap()
    from app.core.database import create_db_engine

    engine = create_db_engine()
    try:
        yield engine
    finally:
        engine.dispose()


def _rewrite_local_app_url(base: str, port: str) -> str:
    parsed = urlparse(base)
    if parsed.hostname not in _LOCAL_API_HOSTS or not port:
        return base
    if parsed.port is not None and str(parsed.port) == port:
        return base
    if parsed.port is None and port in {"80", "443"}:
        return base
    return f"{parsed.scheme}://{parsed.hostname}:{port}"


def api_base_url() -> str:
    bootstrap()
    override = (os.getenv("API_BASE_URL") or "").strip().rstrip("/")
    if override:
        return override

    from app.core.config import settings

    port = os.getenv("PORT", "").strip() or str(settings.port)
    base = _rewrite_local_app_url(settings.app_url.rstrip("/"), port)
    return f"{base}/api/v1"


def app_url_looks_local() -> bool:
    bootstrap()
    from app.core.config import settings

    host = urlparse(settings.app_url).hostname or ""
    return host in _LOCAL_API_HOSTS


@contextmanager
def db_session() -> Iterator:
    bootstrap()
    from app.db.session import _session_factory

    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


def backend_dir() -> Path:
    configured = (os.getenv("BACKEND_DIR") or "").strip()
    if configured:
        return Path(configured)
    return ROOT.parent / "backend"
