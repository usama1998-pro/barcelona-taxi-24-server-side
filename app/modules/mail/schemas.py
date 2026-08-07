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


class ContactInquiryBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=5000)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=60)
    booking_reference: str | None = Field(default=None, alias="bookingReference", max_length=80)

    model_config = {"populate_by_name": True}
