from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.driver import Driver
from app.db.models.user import User
from app.modules.auth.token_revocation import token_revocation
from app.modules.auth.types import (
    AuthenticatedUser,
    JwtPayload,
    JwtPrincipalKind,
    LoginResponse,
    login_response_from_token,
    parse_jwt_expires_in,
)


def extract_access_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    trimmed = authorization.strip()
    if not trimmed:
        return None
    bearer = re.match(r"^Bearer\s+(.+)$", trimmed, re.IGNORECASE)
    if bearer and bearer.group(1):
        token = bearer.group(1).strip()
        nested = re.match(r"^Bearer\s+(.+)$", token, re.IGNORECASE)
        return nested.group(1).strip() if nested else token
    if trimmed.count(".") == 2:
        return trimmed
    return None


def sign_access_token(
    *,
    sub: str,
    email: str,
    typ: JwtPrincipalKind,
    is_admin: bool,
    tv: int,
    is_super_admin: bool | None = None,
) -> LoginResponse:
    now = datetime.now(timezone.utc)
    payload: JwtPayload = {
        "sub": sub,
        "email": email,
        "typ": typ,
        "is_admin": is_admin,
        "tv": tv,
        "jti": str(uuid.uuid4()),
    }
    if typ == "user" and is_super_admin is not None:
        payload["is_super_admin"] = is_super_admin
    expires_delta = parse_jwt_expires_in(settings.jwt_expires_in)
    exp = int((now + expires_delta).timestamp())
    payload["iat"] = int(now.timestamp())
    payload["exp"] = exp
    encoded = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm="HS256",
    )
    return login_response_from_token(encoded, exp)


def validate_jwt_payload(
    session: Session,
    payload: JwtPayload,
) -> AuthenticatedUser:
    sub = payload.get("sub")
    email = payload.get("email")
    typ = payload.get("typ")
    is_admin = payload.get("is_admin")
    if not sub or not email or not typ:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if typ not in ("user", "driver"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if not isinstance(is_admin, bool):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    jti = payload.get("jti")
    if token_revocation.is_revoked(jti if isinstance(jti, str) else None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    raw_tv = payload.get("tv")
    if not isinstance(raw_tv, int) or raw_tv < 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    tv = raw_tv

    staff_is_super_admin: bool | None = None
    if typ == "driver":
        if is_admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        driver = session.get(Driver, sub)
        if not driver or not driver.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Driver account is disabled",
            )
        if driver.token_version != tv:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is no longer valid; sign in again",
            )
    elif typ == "user":
        user = session.get(User, sub)
        if not user or not user.is_admin or not is_admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin account not found",
            )
        payload_super = payload.get("is_super_admin")
        if isinstance(payload_super, bool) and payload_super != user.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is no longer valid; sign in again",
            )
        if user.token_version != tv:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is no longer valid; sign in again",
            )
        staff_is_super_admin = user.is_super_admin

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    now_sec = int(datetime.now(timezone.utc).timestamp())
    expires_in = max(0, exp - now_sec)
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()

    result: AuthenticatedUser = {
        "sub": sub,
        "email": email,
        "typ": typ,
        "is_admin": is_admin,
        "tv": tv,
        "jti": jti if isinstance(jti, str) else None,
        "exp": exp,
        "iat": payload.get("iat") if isinstance(payload.get("iat"), int) else None,
        "expires_in": expires_in,
        "expires_at": expires_at,
    }
    if typ == "user":
        result["is_super_admin"] = staff_is_super_admin or False
    return result


def verify_access_token(session: Session, token: str) -> AuthenticatedUser:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
    return validate_jwt_payload(session, payload)
