from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

JwtPrincipalKind = Literal["user", "driver"]


class JwtPayload(TypedDict, total=False):
    sub: str
    email: str
    typ: JwtPrincipalKind
    is_admin: bool
    is_super_admin: bool
    tv: int
    jti: str
    exp: int
    iat: int


class AuthenticatedUser(TypedDict, total=False):
    sub: str
    email: str
    typ: JwtPrincipalKind
    is_admin: bool
    is_super_admin: bool
    tv: int
    jti: str
    exp: int
    iat: int
    expires_in: int
    expires_at: str


class LoginResponse(TypedDict):
    access_token: str
    expires_in: int
    expires_at: str


def parse_jwt_expires_in(raw: str) -> timedelta:
    value = raw.strip()
    if not value:
        return timedelta(days=365 * 100)
    match = re.fullmatch(r"(\d+)\s*([smhdwy])", value, re.IGNORECASE)
    if not match:
        return timedelta(days=365 * 100)
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(weeks=amount)
    return timedelta(days=365 * amount)


def login_response_from_token(access_token: str, exp: int) -> LoginResponse:
    now_sec = int(datetime.now(timezone.utc).timestamp())
    expires_in = max(0, exp - now_sec)
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
    return {
        "access_token": access_token,
        "expires_in": expires_in,
        "expires_at": expires_at,
    }
