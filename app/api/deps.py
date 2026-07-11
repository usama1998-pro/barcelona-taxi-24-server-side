from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.rate_limit import (
    ADMIN_RATE_LIMIT,
    check_rate_limit,
    client_ip,
    is_admin_throttle_path,
)
from app.core.security import extract_access_token
from app.db.session import get_session
from app.modules.auth.service import auth_service
from app.modules.auth.types import AuthenticatedUser

bearer_scheme = HTTPBearer(auto_error=False)


async def get_optional_bearer(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> str | None:
    if credentials is None:
        return None
    return credentials.credentials


def _authorization_header(
    token: str | None,
    authorization: str | None,
) -> str | None:
    if authorization:
        return authorization
    if token:
        return f"Bearer {token}"
    return None


async def get_optional_current_user(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Depends(get_optional_bearer)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser | None:
    auth_header = _authorization_header(token, authorization)
    if not extract_access_token(auth_header):
        return None
    return auth_service.verify_bearer(session, auth_header)


async def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Depends(get_optional_bearer)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    auth_header = _authorization_header(token, authorization)
    return auth_service.verify_bearer(session, auth_header)


async def require_jwt(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    return user


async def require_staff_admin(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if user.get("typ") != "user" or not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff admin access required",
        )
    # `/api/v1/admin/*` is already counted by AdminRateLimitMiddleware.
    if not is_admin_throttle_path(request.url.path):
        check_rate_limit(f"admin:{client_ip(request)}", limit=ADMIN_RATE_LIMIT)
    return user


async def require_super_admin(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if user.get("typ") != "user" or not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    if not user.get("is_super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    if not is_admin_throttle_path(request.url.path):
        check_rate_limit(f"admin:{client_ip(request)}", limit=ADMIN_RATE_LIMIT)
    return user


async def require_driver_self(
    request: Request,
    user: Annotated[AuthenticatedUser | None, Depends(get_optional_current_user)],
) -> AuthenticatedUser | None:
    if user is None:
        return None

    if user.get("typ") == "user" and user.get("is_admin"):
        return user

    method = request.method.upper()
    driver_id = request.path_params.get("driver_id")
    is_write = method in {"POST", "PATCH", "PUT", "DELETE"}

    if user.get("typ") == "user":
        if driver_id and is_write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Passengers cannot modify driver profiles or cars",
            )
        return user

    if not driver_id:
        return user
    if driver_id != user.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own driver profile and car",
        )
    return user


async def require_users_resource(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if user.get("is_admin"):
        return user
    if user.get("typ") == "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Drivers cannot access passenger user APIs",
        )
    user_id = request.path_params.get("id")
    if user_id and user_id != user.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own user profile",
        )
    return user
