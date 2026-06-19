from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.common.utils.password import without_password
from app.db.models.car import Car
from app.db.models.driver import Driver
from app.db.models.user import User


def _serialize_driver(driver: Driver) -> dict:
    data = {
        "id": driver.id,
        "userId": driver.user_id,
        "name": driver.name,
        "email": driver.email,
        "phone": driver.phone,
        "photoUrl": driver.photo_url,
        "ratingAverage": driver.rating_average,
        "ratingCount": driver.rating_count,
        "isAvailable": driver.is_available,
        "isActive": driver.is_active,
        "tokenVersion": driver.token_version,
    }
    data = without_password(data)
    if driver.car:
        car = driver.car
        data["car"] = {
            "id": car.id,
            "driverId": car.driver_id,
            "carName": car.car_name,
            "carNumber": car.car_number,
            "capacity": car.capacity,
        }
    else:
        data["car"] = None
    return data


class AdminDriverUserLinkService:
    def assign_linked_user(
        self,
        session: Session,
        driver_id: str,
        user_id: str,
    ) -> dict:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )
        driver = session.scalar(
            select(Driver)
            .where(Driver.id == driver_id)
            .options(selectinload(Driver.car))
        )
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver {driver_id} not found",
            )

        other = session.scalar(select(Driver).where(Driver.user_id == user_id))
        if other and other.id != driver_id:
            other.user_id = None

        driver.user_id = user_id
        session.commit()
        session.refresh(driver)
        return _serialize_driver(driver)

    def clear_linked_user(self, session: Session, driver_id: str) -> dict:
        driver = session.scalar(
            select(Driver)
            .where(Driver.id == driver_id)
            .options(selectinload(Driver.car))
        )
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver {driver_id} not found",
            )
        if driver.user_id:
            driver.user_id = None
            session.commit()
            session.refresh(driver)
        return _serialize_driver(driver)


admin_driver_user_link_service = AdminDriverUserLinkService()
