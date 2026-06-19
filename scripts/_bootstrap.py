from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]


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


def api_base_url() -> str:
    bootstrap()
    from app.core.config import settings

    base = settings.app_url.rstrip("/")
    port = os.getenv("PORT", "").strip() or str(settings.port)
    if base in {"http://localhost:3000", "http://127.0.0.1:3000"} and port != "3000":
        base = f"http://localhost:{port}"
    return f"{base}/api/v1"


def backend_dir() -> Path:
    configured = (os.getenv("BACKEND_DIR") or "").strip()
    if configured:
        return Path(configured)
    return ROOT.parent / "backend"
