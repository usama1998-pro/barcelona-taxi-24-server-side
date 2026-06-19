from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SendBookingEmailBody(BaseModel):
    email: EmailStr
    booking_uuid: str | None = Field(default=None, alias="bookingUuid")

    model_config = {"populate_by_name": True}


class SendTestEmailBody(BaseModel):
    email: EmailStr


class ResendBookingEmailsBody(BaseModel):
    booking_uuid: str = Field(alias="bookingUuid")

    model_config = {"populate_by_name": True}
