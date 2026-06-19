from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class CreateDriverBody(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    phone: str = Field(min_length=1)
    password: str = Field(min_length=8)
    photo_url: str | None = Field(default=None, alias="photoUrl")
    is_available: bool | None = Field(default=None, alias="isAvailable")
    is_active: bool | None = Field(default=None, alias="isActive")

    model_config = {"populate_by_name": True}


class UpdateDriverBody(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=1)
    password: str | None = Field(default=None, min_length=8)
    photo_url: str | None = Field(default=None, alias="photoUrl")
    is_available: bool | None = Field(default=None, alias="isAvailable")
    is_active: bool | None = Field(default=None, alias="isActive")

    model_config = {"populate_by_name": True}


class PatchMyAvailabilityBody(BaseModel):
    is_available: bool = Field(alias="isAvailable")

    model_config = {"populate_by_name": True}


class CreateCarBody(BaseModel):
    car_name: str = Field(alias="carName")
    car_number: str = Field(alias="carNumber")
    capacity: int = Field(ge=1)

    model_config = {"populate_by_name": True}


class UpdateCarBody(BaseModel):
    car_name: str | None = Field(default=None, alias="carName")
    car_number: str | None = Field(default=None, alias="carNumber")
    capacity: int | None = Field(default=None, ge=1)

    model_config = {"populate_by_name": True}
