from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import get_optional_bearer, require_jwt
from app.db.session import get_session
from app.modules.auth.schemas import SigninBody, SignupBody, VerifyCodeBody
from app.modules.auth.service import auth_service
from app.modules.auth.types import AuthenticatedUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/verify-code")
async def verify_code(
    body: VerifyCodeBody,
    session: Annotated[Session, Depends(get_session)],
):
    return auth_service.verify_code(session, body)


@router.post("/signin")
async def signin(
    body: SigninBody,
    session: Annotated[Session, Depends(get_session)],
):
    return auth_service.signin(session, body)


@router.post("/signup")
async def signup(
    body: SignupBody,
    session: Annotated[Session, Depends(get_session)],
):
    return auth_service.signup(session, body)


@router.post("/signout")
async def signout(
    token: Annotated[str | None, Depends(get_optional_bearer)],
    authorization: Annotated[str | None, Header()] = None,
):
    auth_header = authorization or (f"Bearer {token}" if token else None)
    return auth_service.signout(auth_header)


@router.get("/verify")
async def verify(user: Annotated[AuthenticatedUser, Depends(require_jwt)]):
    return user
