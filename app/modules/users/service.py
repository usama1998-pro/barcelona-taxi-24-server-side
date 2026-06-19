from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.utils.password import hash_password
from app.db.models.user import User
from app.modules.auth.types import AuthenticatedUser
from app.modules.users.schemas import UpdateUserBody


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "fullName": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "isAdmin": user.is_admin,
        "isSuperAdmin": user.is_super_admin,
        "tokenVersion": user.token_version,
        "createdAt": user.created_at.isoformat(),
    }


class UsersService:
    def find_all(self, session: Session, requester: AuthenticatedUser) -> list[dict]:
        if requester.get("is_admin"):
            rows = session.scalars(
                select(User).order_by(User.created_at.desc())
            ).all()
            return [serialize_user(row) for row in rows]

        if requester.get("typ") == "driver":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Drivers cannot list users",
            )

        row = session.get(User, requester["sub"])
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {requester['sub']} not found",
            )
        return [serialize_user(row)]

    def find_one(self, session: Session, user_id: str) -> dict:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )
        return serialize_user(user)

    def update(self, session: Session, user_id: str, dto: UpdateUserBody) -> dict:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        if dto.full_name is not None:
            user.full_name = dto.full_name
        if dto.email is not None:
            user.email = dto.email
        if dto.phone is not None:
            user.phone = dto.phone
        if dto.password is not None:
            user.password = hash_password(dto.password)

        try:
            session.commit()
            session.refresh(user)
            return serialize_user(user)
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email or phone is already in use",
            ) from exc

    def remove(self, session: Session, user_id: str) -> None:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )
        session.delete(user)
        session.commit()


users_service = UsersService()
