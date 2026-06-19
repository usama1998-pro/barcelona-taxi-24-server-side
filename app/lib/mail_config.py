from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    secure: bool
    user: str
    password: str
    from_name: str


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in {"0", "false", "no", "off"}


def is_smtp_configured() -> bool:
    host = (os.getenv("SMTP_HOST") or "").strip()
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or "").strip()
    return bool(host and user and password)


def _resolve_smtp_host() -> str | None:
    host = (os.getenv("SMTP_HOST") or "").strip()
    if not host:
        return None
    lower = host.lower()
    if lower.startswith("imap."):
        return f"smtp.{host[5:]}"
    if "hostinger" in lower and not lower.startswith("smtp."):
        return "smtp.hostinger.com"
    return host


def _resolve_smtp_port(host: str) -> int:
    port_raw = (os.getenv("SMTP_PORT") or "").strip()
    port = int(port_raw) if port_raw else 465
    if port == 456 and "hostinger" in host.lower():
        return 465
    return port


def get_smtp_port_warning() -> str | None:
    port_raw = (os.getenv("SMTP_PORT") or "").strip()
    if port_raw == "456":
        return "SMTP_PORT=456 is invalid for Hostinger; use 465 (SSL) or 587 (STARTTLS)."
    return None


def get_booking_notify_email() -> str | None:
    notify = (os.getenv("BOOKING_NOTIFY_EMAIL") or "").strip().lower()
    if notify:
        return notify
    smtp_user = (os.getenv("SMTP_USER") or "").strip().lower()
    if "@" in smtp_user:
        return smtp_user
    super_admin = (os.getenv("SUPER_ADMIN_EMAIL") or "").strip().lower()
    return super_admin or None


def get_smtp_config() -> SmtpConfig | None:
    if not is_smtp_configured():
        return None
    host = _resolve_smtp_host()
    if not host:
        return None
    port = _resolve_smtp_port(host)
    secure_raw = (os.getenv("SMTP_SECURE") or "").strip().lower()
    secure = secure_raw not in {"0", "false"}
    return SmtpConfig(
        host=host,
        port=port,
        secure=True if port == 465 else secure,
        user=os.getenv("SMTP_USER", "").strip(),
        password=os.getenv("SMTP_PASS", "").strip(),
        from_name=(os.getenv("MAIL_FROM_NAME") or "BarcelonaTaxi24").strip(),
    )
