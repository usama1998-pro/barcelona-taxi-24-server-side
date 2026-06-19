from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UpdateUserBody(BaseModel):
    full_name: str | None = Field(default=None, alias="fullName")
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=1)
    password: str | None = Field(default=None, min_length=8)

    model_config = {"populate_by_name": True}
