from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class BookingTimeScope(str, Enum):
    past = "past"
    current = "current"
    upcoming = "upcoming"


class CreateBookingBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    user_id: str | None = Field(default=None, alias="userId")
    driver_id: str | None = Field(default=None, alias="driverId")
    booking_reference: str | None = Field(default=None, alias="bookingReference", max_length=120)
    pickup_location: dict[str, Any] = Field(alias="pickupLocation")
    dropoff_location: dict[str, Any] = Field(alias="dropoffLocation")
    scheduled_time: str = Field(alias="scheduledTime")
    price: float
    status: str
    luggage_count: int = Field(alias="luggageCount", ge=0, le=50)
    passenger_count: int = Field(alias="passengerCount", ge=1, le=20)
    infant_carrier_count: int | None = Field(default=None, alias="infantCarrierCount", ge=0, le=4)
    child_seat_count: int | None = Field(default=None, alias="childSeatCount", ge=0, le=4)
    booster_count: int | None = Field(default=None, alias="boosterCount", ge=0, le=4)
    customer_name: str | None = Field(default=None, alias="customerName")
    customer_email: EmailStr | None = Field(default=None, alias="customerEmail")
    customer_phone: str | None = Field(default=None, alias="customerPhone")
    flight_number: str | None = Field(default=None, alias="flightNumber")
    return_time: str | None = Field(default=None, alias="returnTime")
    note: str | None = None
    driver_list_label: str | None = Field(
        default=None,
        alias="driverListLabel",
        max_length=48,
    )


class UpdateBookingBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    user_id: str | None = Field(default=None, alias="userId")
    driver_id: str | None = Field(default=None, alias="driverId")
    booking_reference: str | None = Field(default=None, alias="bookingReference", max_length=120)
    pickup_location: dict[str, Any] | None = Field(default=None, alias="pickupLocation")
    dropoff_location: dict[str, Any] | None = Field(default=None, alias="dropoffLocation")
    scheduled_time: str | None = Field(default=None, alias="scheduledTime")
    price: float | None = None
    status: str | None = None
    luggage_count: int | None = Field(default=None, alias="luggageCount", ge=0, le=50)
    passenger_count: int | None = Field(default=None, alias="passengerCount", ge=1, le=20)
    infant_carrier_count: int | None = Field(default=None, alias="infantCarrierCount", ge=0, le=4)
    child_seat_count: int | None = Field(default=None, alias="childSeatCount", ge=0, le=4)
    booster_count: int | None = Field(default=None, alias="boosterCount", ge=0, le=4)
    customer_name: str | None = Field(default=None, alias="customerName")
    customer_email: EmailStr | None = Field(default=None, alias="customerEmail")
    customer_phone: str | None = Field(default=None, alias="customerPhone")
    flight_number: str | None = Field(default=None, alias="flightNumber")
    return_time: str | None = Field(default=None, alias="returnTime")
    note: str | None = None
    driver_list_label: str | None = Field(
        default=None,
        alias="driverListLabel",
        max_length=48,
    )


class ListBookingsQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    time_scope: BookingTimeScope | None = Field(default=None, alias="timeScope")
    scheduled_on: str | None = Field(default=None, alias="scheduledOn")
    booking_reference: str | None = Field(default=None, alias="bookingReference", max_length=64)

    @field_validator("scheduled_on")
    @classmethod
    def validate_scheduled_on(cls, value: str | None) -> str | None:
        if value is None:
            return None
        import re

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("scheduledOn must be YYYY-MM-DD")
        return value
