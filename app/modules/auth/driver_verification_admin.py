from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.utils.ids import new_id
from app.db.models.driver import Driver
from app.db.models.driver_verification_code import DriverVerificationCode
from app.db.models.user import User


class DriverVerificationAdminService:
    @staticmethod
    def _normalize_code(raw: str) -> str:
        return re.sub(r"\D", "", raw)[:4]

    def _find_driver_by_email_strict(self, session: Session, driver_email: str) -> Driver:
        email = driver_email.strip().lower()
        driver = session.scalar(select(Driver).where(Driver.email == email))
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found for that email",
            )
        return driver

    def _find_driver_or_provision_from_user(
        self,
        session: Session,
        driver_email: str,
    ) -> Driver:
        email = driver_email.strip().lower()
        existing = session.scalar(select(Driver).where(Driver.email == email))
        if existing:
            return existing

        user = session.scalar(select(User).where(User.email == email))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No driver or user found for that email",
            )
        try:
            driver = Driver(
                id=new_id(),
                user_id=user.id,
                name=user.full_name,
                email=user.email,
                phone=user.phone,
                password=user.password,
                is_available=True,
                is_active=True,
                token_version=0,
            )
            session.add(driver)
            session.flush()
            return driver
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot create driver profile for this user: "
                    "email or phone already used on another driver"
                ),
            ) from exc

    def set_for_driver_email(
        self,
        session: Session,
        *,
        driver_email: str,
        code: str,
        is_active: bool | None = None,
    ) -> dict:
        normalized = self._normalize_code(code)
        if not re.fullmatch(r"\d{4}", normalized):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code must be exactly 4 digits",
            )
        driver = self._find_driver_or_provision_from_user(session, driver_email)
        taken = session.scalar(
            select(DriverVerificationCode).where(DriverVerificationCode.code == normalized)
        )
        if taken and taken.driver_id != driver.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That code is already assigned to another driver",
            )

        active = is_active if is_active is not None else True
        now = datetime.now(timezone.utc)
        row = session.scalar(
            select(DriverVerificationCode).where(
                DriverVerificationCode.driver_id == driver.id
            )
        )
        if row:
            row.code = normalized
            row.is_active = active
            row.updated_at = now
        else:
            row = DriverVerificationCode(
                id=new_id(),
                driver_id=driver.id,
                code=normalized,
                is_active=active,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "driverId": driver.id,
            "driverEmail": driver.email,
            "driverName": driver.name,
            "code": row.code,
            "isActive": row.is_active,
        }

    def update_for_driver_email(
        self,
        session: Session,
        *,
        driver_email: str,
        code: str | None = None,
        is_active: bool | None = None,
    ) -> dict:
        driver = self._find_driver_or_provision_from_user(session, driver_email)
        existing = session.scalar(
            select(DriverVerificationCode).where(
                DriverVerificationCode.driver_id == driver.id
            )
        )
        if not existing:
            if code is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "No verification code yet for this driver; send a 4-digit code "
                        "(or use POST to set one)."
                    ),
                )
            return self.set_for_driver_email(
                session,
                driver_email=driver_email,
                code=code,
                is_active=is_active,
            )

        next_code = self._normalize_code(code) if code is not None else None
        if next_code is not None and not re.fullmatch(r"\d{4}", next_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code must be exactly 4 digits",
            )
        if next_code is None and is_active is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide code and/or isActive to update",
            )
        if next_code is not None:
            taken = session.scalar(
                select(DriverVerificationCode).where(
                    DriverVerificationCode.code == next_code
                )
            )
            if taken and taken.driver_id != driver.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="That code is already assigned to another driver",
                )

        if next_code is not None:
            existing.code = next_code
        if is_active is not None:
            existing.is_active = is_active
        existing.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(existing)
        return {
            "driverId": existing.driver_id,
            "driverEmail": driver.email,
            "driverName": driver.name,
            "code": existing.code,
            "isActive": existing.is_active,
        }

    def set_active(self, session: Session, driver_id: str, is_active: bool) -> dict:
        row = session.scalar(
            select(DriverVerificationCode).where(
                DriverVerificationCode.driver_id == driver_id
            )
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No verification code configured for this driver",
            )
        row.is_active = is_active
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        return {
            "driverId": row.driver_id,
            "code": row.code,
            "isActive": row.is_active,
        }

    def remove(self, session: Session, driver_id: str) -> dict:
        row = session.scalar(
            select(DriverVerificationCode).where(
                DriverVerificationCode.driver_id == driver_id
            )
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No verification code configured for this driver",
            )
        session.delete(row)
        session.commit()
        return {"deleted": True}

    def remove_by_driver_email(self, session: Session, driver_email: str) -> dict:
        driver = self._find_driver_by_email_strict(session, driver_email)
        return self.remove(session, driver.id)


driver_verification_admin_service = DriverVerificationAdminService()
