from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class HostingerInboxConfig:
    host: str
    port: int
    user: str
    password: str
    mailbox: str


DEFAULT_IMAP_PORT = 993


def _read_shared_mailbox_credentials() -> tuple[str, str] | None:
    user = (os.getenv("IMAP_USER") or os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("IMAP_PASS") or os.getenv("SMTP_PASS") or "").strip()
    if not user or not password:
        return None
    return user, password


def _resolve_imap_host() -> str | None:
    explicit = (os.getenv("IMAP_HOST") or "").strip()
    if explicit:
        return explicit

    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    if not smtp_host:
        return None

    lower = smtp_host.lower()
    if "hostinger" in lower:
        return "imap.hostinger.com"
    if lower.startswith("smtp."):
        return f"imap.{smtp_host[5:]}"
    if lower.startswith("imap."):
        return smtp_host
    return smtp_host


def is_imap_configured() -> bool:
    return get_hostinger_inbox_config() is not None


def get_hostinger_inbox_config() -> HostingerInboxConfig | None:
    host = _resolve_imap_host()
    auth = _read_shared_mailbox_credentials()
    if not host or not auth:
        return None

    port_raw = (os.getenv("IMAP_PORT") or "").strip()
    port = int(port_raw) if port_raw else DEFAULT_IMAP_PORT
    if not port:
        port = DEFAULT_IMAP_PORT

    return HostingerInboxConfig(
        host=host,
        port=port,
        user=auth[0],
        password=auth[1],
        mailbox=(os.getenv("IMAP_MAILBOX") or "INBOX").strip(),
    )
