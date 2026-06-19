from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fpdf import FPDF

from app.db.enums import InvoiceAddressKind

COMPANY_NAME = "BarcelonaTaxi24"
COMPANY_LINES = [
    "Barcelona International Airport, 08820 El Prat de Llobregat, Barcelona, Spain",
    "0034663619000",
    "www.taxibarcelona24.com",
    "info@taxibarcelona24.com",
]
TERMS_TEXT = "Payment received via bank transfer"
# Core PDF fonts (Helvetica) are Latin-1 only; avoid Unicode like € or em dash.
_EMPTY = "-"


def _format_money(amount: float) -> str:
    return f"{amount:,.2f}"


def _format_euro(amount: float) -> str:
    return f"EUR {_format_money(amount)}"


def _format_endpoint(
    kind: str,
    address: str | None,
    airline: str | None,
    flight_no: str | None,
) -> str:
    if kind == InvoiceAddressKind.LOCATION.value:
        return (address or "").strip() or _EMPTY
    airline_text = (airline or "").strip()
    flight_text = (flight_no or "").strip()
    if not airline_text and not flight_text:
        return _EMPTY
    return " / ".join(part for part in (airline_text, flight_text) if part)


def _invoice_display_number(invoice_id: str) -> str:
    hex_value = invoice_id.replace("-", "")[:12]
    try:
        number = int(hex_value, 16)
    except ValueError:
        return invoice_id.replace("-", "")[:8].upper()
    return str((number % 900000) + 100000)


def _invoice_date_ymd(iso_value: str) -> str:
    tz_name = os.environ.get("TZ", "Europe/Madrid")
    try:
        parsed = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        return iso_value[:10]
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Madrid")
    return parsed.astimezone(tz).strftime("%Y-%m-%d")


def _transfer_description(pickup: str, dropoff: str) -> str:
    pickup_text = "" if pickup.strip() == _EMPTY else pickup.strip()
    dropoff_text = "" if dropoff.strip() == _EMPTY else dropoff.strip()
    if not pickup_text and not dropoff_text:
        return "Transfer"
    if pickup_text and dropoff_text:
        return f"Transfer from {pickup_text} to {dropoff_text}"
    if pickup_text:
        return f"Transfer from {pickup_text}"
    return f"Transfer to {dropoff_text}"


def build_driver_invoice_pdf(inv: dict[str, Any]) -> bytes:
    pickup = _format_endpoint(
        inv["pickupKind"],
        inv.get("pickupAddress"),
        inv.get("pickupAirline"),
        inv.get("pickupFlightNo"),
    )
    dropoff = _format_endpoint(
        inv["dropoffKind"],
        inv.get("dropoffAddress"),
        inv.get("dropoffAirline"),
        inv.get("dropoffFlightNo"),
    )
    gross = float(inv["priceAmount"])
    tax = float(inv["taxAmount"])
    net = float(inv["totalAmount"])

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_left_margin(18)
    pdf.set_right_margin(18)

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, COMPANY_NAME, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    for line in COMPANY_LINES:
        pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    left_x = pdf.get_x()
    right_x = 110
    y_start = pdf.get_y()

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(left_x, y_start)
    pdf.cell(80, 6, "BILL TO")
    pdf.set_xy(right_x, y_start)
    pdf.cell(80, 6, "INVOICE #")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(left_x, y_start + 8)
    pdf.cell(80, 6, inv["fullName"])
    pdf.set_xy(right_x, y_start + 8)
    pdf.cell(80, 6, _invoice_display_number(inv["id"]))

    pdf.set_xy(left_x, y_start + 16)
    pdf.cell(80, 6, inv["phoneNumber"])
    pdf.set_xy(left_x, y_start + 24)
    pdf.cell(80, 6, inv["bookingReference"])
    passenger_count = int(inv["passengerCount"])
    pax_label = "1 passenger" if passenger_count == 1 else f"{passenger_count} passengers"
    pdf.set_xy(left_x, y_start + 32)
    pdf.cell(80, 6, pax_label)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(right_x, y_start + 16)
    pdf.cell(80, 6, "INVOICE DATE")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(right_x, y_start + 24)
    pdf.cell(80, 6, _invoice_date_ymd(inv["pickupDate"]))

    pdf.set_y(y_start + 44)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.8)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(8)

    def row_money(label: str, amount: float) -> None:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(120, 8, label)
        pdf.cell(0, 8, _format_euro(amount), align="R", new_x="LMARGIN", new_y="NEXT")

    row_money("PRICE", net)
    row_money("10% TAX", tax)
    row_money("TOTAL", gross)
    pdf.ln(4)

    pdf.set_draw_color(204, 204, 204)
    pdf.set_line_width(0.3)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(120, 6, "Description")
    pdf.cell(0, 6, "Amount", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    description = _transfer_description(pickup, dropoff)
    pdf.cell(120, 6, description)
    pdf.cell(0, 6, _format_money(gross), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    child_seats = (inv.get("childSeatsSummary") or "").strip()
    if child_seats:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(68, 68, 68)
        pdf.multi_cell(0, 5, f"Child seats: {child_seats}")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "TERMS AND CONDITIONS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, TERMS_TEXT)

    return bytes(pdf.output())
