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

    return settings.app_url.rstrip("/")


def backend_dir() -> Path:
    configured = (os.getenv("BACKEND_DIR") or "").strip()
    if configured:
        return Path(configured)
    return ROOT.parent / "backend"
