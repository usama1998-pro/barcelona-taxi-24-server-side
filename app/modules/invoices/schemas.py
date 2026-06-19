from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.enums import InvoiceAddressKind


class CreateDriverInvoiceBody(BaseModel):
    full_name: str = Field(alias="fullName", min_length=1, max_length=200)
    phone_number: str = Field(alias="phoneNumber", min_length=5, max_length=40)
    booking_reference: str = Field(alias="bookingReference", min_length=1, max_length=120)
    pickup_date: datetime = Field(alias="pickupDate")
    pickup_kind: InvoiceAddressKind = Field(alias="pickupKind")
    pickup_address: str | None = Field(default=None, alias="pickupAddress", max_length=500)
    pickup_airline: str | None = Field(default=None, alias="pickupAirline", max_length=120)
    pickup_flight_no: str | None = Field(default=None, alias="pickupFlightNo", max_length=40)
    dropoff_kind: InvoiceAddressKind = Field(alias="dropoffKind")
    dropoff_address: str | None = Field(default=None, alias="dropoffAddress", max_length=500)
    dropoff_airline: str | None = Field(default=None, alias="dropoffAirline", max_length=120)
    dropoff_flight_no: str | None = Field(default=None, alias="dropoffFlightNo", max_length=40)
    passenger_count: int = Field(alias="passengerCount", ge=1, le=25)
    price_amount: float = Field(alias="priceAmount", ge=0)
    child_seats_summary: str | None = Field(
        default=None,
        alias="childSeatsSummary",
        max_length=500,
    )

    model_config = {"populate_by_name": True}


class ListDriverInvoicesQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)

    model_config = {"populate_by_name": True}
