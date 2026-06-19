from __future__ import annotations

from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.utils.ids import new_id
from app.common.utils.password import hash_password, verify_password
from app.core.security import extract_access_token, sign_access_token, verify_access_token
from app.db.models.driver import Driver
from app.db.models.driver_verification_code import DriverVerificationCode
from app.db.models.user import User
from app.modules.auth.schemas import SigninBody, SignupBody, VerifyCodeBody
from app.modules.auth.token_revocation import token_revocation
from app.modules.auth.types import AuthenticatedUser, LoginResponse


class AuthService:
    def signin(self, session: Session, dto: SigninBody) -> LoginResponse:
        email = dto.email.strip().lower()
        user = session.scalar(select(User).where(User.email == email))
        driver = session.scalar(select(Driver).where(Driver.email == email))

        if user and user.is_admin and verify_password(dto.password, user.password):
            return sign_access_token(
                sub=user.id,
                email=user.email,
                typ="user",
                is_admin=True,
                is_super_admin=user.is_super_admin,
                tv=user.token_version,
            )

        if driver:
            if not verify_password(dto.password, driver.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                )
            if not driver.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Driver account is disabled",
                )
            return sign_access_token(
                sub=driver.id,
                email=driver.email,
                typ="driver",
                is_admin=False,
                tv=driver.token_version,
            )

        if not user or not verify_password(dto.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Passenger accounts cannot sign in here; "
                "use npm run create-admin for staff accounts"
            ),
        )

    def verify_code(self, session: Session, dto: VerifyCodeBody) -> LoginResponse:
        code = dto.code.strip()
        match = session.scalar(
            select(DriverVerificationCode)
            .where(DriverVerificationCode.code == code)
        )
        if not match or not match.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verification code",
            )
        driver = session.get(Driver, match.driver_id)
        if not driver or not driver.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Driver account is disabled",
            )
        return sign_access_token(
            sub=driver.id,
            email=driver.email,
            typ="driver",
            is_admin=False,
            tv=driver.token_version,
        )

    def verify_bearer(
        self,
        session: Session,
        authorization: str | None,
    ) -> AuthenticatedUser:
        token = extract_access_token(authorization)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Missing access token: send Authorization: Bearer <access_token>, "
                    "or in Swagger use Authorize and paste only the token."
                ),
            )
        return verify_access_token(session, token)

    def signout(self, authorization: str | None) -> dict[str, bool]:
        from app.core.config import settings

        token = extract_access_token(authorization)
        if not token:
            return {"revoked": False}
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from None
        jti = payload.get("jti")
        exp = payload.get("exp")
        if isinstance(exp, int) and isinstance(jti, str):
            token_revocation.revoke_until(jti, exp)
            return {"revoked": True}
        return {"revoked": False}

    def signup(self, session: Session, dto: SignupBody) -> LoginResponse:
        password_hash = hash_password(dto.password)
        email = dto.email.strip().lower()
        now = datetime.now(timezone.utc)

        user = User(
            id=new_id(),
            full_name=dto.name,
            email=email,
            phone=dto.phone,
            password=password_hash,
            is_admin=False,
            is_super_admin=False,
            token_version=0,
            created_at=now,
        )
        session.add(user)
        session.flush()

        driver = Driver(
            id=new_id(),
            user_id=user.id,
            name=dto.name,
            email=email,
            phone=dto.phone,
            password=password_hash,
            photo_url=dto.photo_url,
            is_available=dto.is_available if dto.is_available is not None else True,
            is_active=True,
            token_version=0,
        )
        session.add(driver)
        session.commit()

        return sign_access_token(
            sub=driver.id,
            email=driver.email,
            typ="driver",
            is_admin=False,
            tv=0,
        )


auth_service = AuthService()
