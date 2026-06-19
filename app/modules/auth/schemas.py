from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SigninBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class SignupBody(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    phone: str = Field(min_length=1)
    password: str = Field(min_length=6)
    photo_url: str | None = Field(default=None, alias="photoUrl")
    is_available: bool | None = Field(default=None, alias="isAvailable")

    model_config = {"populate_by_name": True}


class VerifyCodeBody(BaseModel):
    code: str = Field(min_length=1)


class SetVerificationCodeBody(BaseModel):
    driver_email: str = Field(alias="driverEmail")
    code: str
    is_active: bool | None = Field(default=None, alias="isActive")

    model_config = {"populate_by_name": True}


class UpdateVerificationCodeBody(BaseModel):
    driver_email: str = Field(alias="driverEmail")
    code: str | None = None
    is_active: bool | None = Field(default=None, alias="isActive")

    model_config = {"populate_by_name": True}


class SetVerificationActiveBody(BaseModel):
    is_active: bool = Field(alias="isActive")

    model_config = {"populate_by_name": True}


class AssignLinkedUserBody(BaseModel):
    user_id: str = Field(alias="userId")

    model_config = {"populate_by_name": True}
