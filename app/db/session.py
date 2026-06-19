from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from app.core.database import create_db_engine


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_db_engine(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def get_session() -> Generator[Session, None, None]:
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
