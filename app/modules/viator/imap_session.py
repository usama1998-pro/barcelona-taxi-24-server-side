from __future__ import annotations

import imaplib
import logging
import os
from collections.abc import Callable
from typing import TypeVar

from app.lib.viator_inbox_config import HostingerInboxConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_CONNECTION_TIMEOUT_MS = 120_000


def _resolve_imap_timeout_ms() -> int:
    raw = (os.getenv("IMAP_SOCKET_TIMEOUT_MS") or "").strip()
    if not raw:
        return DEFAULT_CONNECTION_TIMEOUT_MS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_CONNECTION_TIMEOUT_MS
    return parsed if parsed >= 30_000 else DEFAULT_CONNECTION_TIMEOUT_MS


def with_imap_session(cfg: HostingerInboxConfig, fn: Callable[[imaplib.IMAP4_SSL], T]) -> T:
    timeout_sec = _resolve_imap_timeout_ms() / 1000
    client = imaplib.IMAP4_SSL(cfg.host, cfg.port, timeout=timeout_sec)
    try:
        client.login(cfg.user, cfg.password)
        return fn(client)
    finally:
        try:
            client.logout()
        except Exception:
            pass


def select_mailbox(client: imaplib.IMAP4_SSL, mailbox: str) -> None:
    status, _ = client.select(mailbox, readonly=False)
    if status != "OK":
        raise RuntimeError(f"Could not select mailbox {mailbox}")
