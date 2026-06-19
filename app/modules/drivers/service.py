from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.common.utils.ids import new_id
from app.common.utils.password import hash_password
from app.db.models.car import Car
from app.db.models.driver import Driver
from app.db.models.user import User
from app.modules.auth.types import AuthenticatedUser
from app.modules.drivers.schemas import (
    CreateCarBody,
    CreateDriverBody,
    UpdateCarBody,
    UpdateDriverBody,
)


def serialize_car(car: Car) -> dict:
    return {
        "id": car.id,
        "driverId": car.driver_id,
        "carName": car.car_name,
        "carNumber": car.car_number,
        "capacity": car.capacity,
    }


def serialize_driver_public(driver: Driver, *, car: Car | None = None) -> dict:
    payload: dict = {
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
    }
    if car is not None:
        payload["car"] = serialize_car(car) if car else None
    return payload


def serialize_driver_with_car(driver: Driver) -> dict:
    return {
        **serialize_driver_public(driver),
        "car": serialize_car(driver.car) if driver.car else None,
    }


def serialize_profile_user(user: User) -> dict:
    return {
        "id": user.id,
        "fullName": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "isAdmin": user.is_admin,
        "createdAt": user.created_at.isoformat(),
    }


class DriversService:
    def create(self, session: Session, dto: CreateDriverBody) -> dict:
        try:
            password_hash = hash_password(dto.password)
            email = dto.email.strip().lower()
            user = User(
                id=new_id(),
                full_name=dto.name,
                email=email,
                phone=dto.phone,
                password=password_hash,
                is_admin=False,
                is_super_admin=False,
                token_version=0,
                created_at=datetime.now(timezone.utc),
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
                is_active=dto.is_active if dto.is_active is not None else True,
                token_version=0,
            )
            session.add(driver)
            session.commit()
            session.refresh(driver)
            return serialize_driver_public(driver)
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email or phone is already registered",
            ) from exc

    def find_all(self, session: Session, requester: AuthenticatedUser) -> list[dict]:
        if requester.get("typ") == "driver":
            driver = session.scalar(
                select(Driver)
                .where(Driver.id == requester["sub"])
                .options(selectinload(Driver.car))
            )
            if not driver:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Driver {requester['sub']} not found",
                )
            return [serialize_driver_with_car(driver)]

        rows = session.scalars(
            select(Driver)
            .order_by(Driver.name.asc())
            .options(selectinload(Driver.car))
        ).all()
        return [serialize_driver_with_car(row) for row in rows]

    def find_one(self, session: Session, driver_id: str) -> dict:
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
        return serialize_driver_with_car(driver)

    def patch_my_availability(
        self,
        session: Session,
        requester: AuthenticatedUser,
        is_available: bool,
    ) -> dict:
        if requester.get("typ") != "driver":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only drivers can update availability",
            )
        driver = session.get(Driver, requester["sub"])
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver {requester['sub']} not found",
            )
        driver.is_available = is_available
        session.commit()
        return {"isAvailable": is_available}

    def get_my_profile(self, session: Session, requester: AuthenticatedUser) -> dict:
        if requester.get("typ") != "driver":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only drivers can access this endpoint",
            )
        driver = session.scalar(
            select(Driver)
            .where(Driver.id == requester["sub"])
            .options(selectinload(Driver.car), selectinload(Driver.user))
        )
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver {requester['sub']} not found",
            )
        return {
            **serialize_driver_public(driver),
            "car": serialize_car(driver.car) if driver.car else None,
            "user": serialize_profile_user(driver.user) if driver.user else None,
        }

    def update(
        self,
        session: Session,
        driver_id: str,
        dto: UpdateDriverBody,
    ) -> dict:
        driver = session.get(Driver, driver_id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver {driver_id} not found",
            )

        if dto.name is not None:
            driver.name = dto.name
        if dto.email is not None:
            driver.email = dto.email.strip().lower()
        if dto.phone is not None:
            driver.phone = dto.phone
        if dto.password is not None:
            driver.password = hash_password(dto.password)
        if dto.photo_url is not None:
            driver.photo_url = dto.photo_url
        if dto.is_available is not None:
            driver.is_available = dto.is_available
        if dto.is_active is not None:
            driver.is_active = dto.is_active

        try:
            session.commit()
            session.refresh(driver)
            return serialize_driver_public(driver)
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email or phone is already in use",
            ) from exc

    def remove(self, session: Session, driver_id: str) -> None:
        driver = session.get(Driver, driver_id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver {driver_id} not found",
            )
        session.delete(driver)
        session.commit()

    def create_car(
        self,
        session: Session,
        driver_id: str,
        dto: CreateCarBody,
    ) -> dict:
        driver = session.get(Driver, driver_id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver {driver_id} not found",
            )
        existing = session.scalar(select(Car).where(Car.driver_id == driver_id))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Driver {driver_id} already has a car; "
                    "update or delete it first"
                ),
            )
        try:
            car = Car(
                id=new_id(),
                driver_id=driver_id,
                car_name=dto.car_name,
                car_number=dto.car_number,
                capacity=dto.capacity,
            )
            session.add(car)
            session.commit()
            session.refresh(car)
            return serialize_car(car)
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Car number is already registered",
            ) from exc

    def get_car(self, session: Session, driver_id: str) -> dict:
        driver = session.get(Driver, driver_id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver {driver_id} not found",
            )
        car = session.scalar(select(Car).where(Car.driver_id == driver_id))
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No car registered for driver {driver_id}",
            )
        return serialize_car(car)

    def update_car(
        self,
        session: Session,
        driver_id: str,
        dto: UpdateCarBody,
    ) -> dict:
        car = session.scalar(select(Car).where(Car.driver_id == driver_id))
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No car registered for driver {driver_id}",
            )
        if dto.car_name is not None:
            car.car_name = dto.car_name
        if dto.car_number is not None:
            car.car_number = dto.car_number
        if dto.capacity is not None:
            car.capacity = dto.capacity
        try:
            session.commit()
            session.refresh(car)
            return serialize_car(car)
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Car number is already in use",
            ) from exc

    def remove_car(self, session: Session, driver_id: str) -> None:
        car = session.scalar(select(Car).where(Car.driver_id == driver_id))
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No car registered for driver {driver_id}",
            )
        session.delete(car)
        session.commit()


drivers_service = DriversService()
