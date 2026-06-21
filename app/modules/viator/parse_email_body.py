from __future__ import annotations

import re
from typing import Any

from mailparser import parse_from_bytes

from app.common.utils.phone import normalize_phone_number
from app.lib.viator_allowed_products import normalize_viator_product_code
from app.modules.viator.booking_fields import ViatorBookingDetails

_VIATOR_INLINE_FIELDS: list[tuple[str, list[str]]] = [
    ("productName", ["Tour Name"]),
    (
        "leadTraveler",
        [
            "Lead Traveler Name",
            "Lead Traveller Name",
            "Lead Traveler",
            "Lead Traveller",
        ],
    ),
    ("travelerNames", ["Traveler Names"]),
    ("travelers", ["Travelers"]),
    ("tourGrade", ["Tour Grade Description", "Tour Grade"]),
    ("tourGradeCode", ["Tour Grade Code"]),
    ("language", ["Tour Language"]),
    ("cruiseShipName", ["Cruise Ship Name", "Cruise Ship"]),
    (
        "pickupLocation",
        ["Hotel Pickup", "Pickup Location", "Meeting Point", "Port Pickup"],
    ),
    (
        "arrivalFlightNo",
        [
            "Arrival Flight No",
            "Arrival Flight No.",
            "Arrival Flight Number",
            "Arrival Flight #",
            "Arrival Flight",
        ],
    ),
    ("arrivalAirline", ["Arrival Airline"]),
    ("arrivalTime", ["Arrival Time"]),
    ("disembarkationTime", ["Disembarkation Time", "Disembarkment Time"]),
    (
        "departureFlightNo",
        [
            "Departure Flight No",
            "Departure Flight No.",
            "Departure Flight Number",
            "Departure Flight #",
            "Departure Flight",
        ],
    ),
    ("departureTime", ["Departure Time"]),
    ("departureAirline", ["Departure Airline"]),
    (
        "dropoffLocation",
        [
            "Drop Off Location",
            "Drop-off Location",
            "Dropoff Location",
            "Drop Off Location Name",
            "Drop-off Location Name",
            "Dropoff Location Name",
            "Drop Off Point",
            "Drop-off Point",
            "Dropoff Point",
            "Destination",
            "Port Drop Off",
            "Port Drop-off",
            "Port Dropoff",
        ],
    ),
    ("specialRequirements", ["Special Requirements", "Special Requests"]),
]

_BOUNDARY_LABELS = [
    "Booking Reference",
    "Travel Date",
    "Date",
    "Product Code",
    "Location",
    "Net Rate",
    "Boarding Time",
    "Phone",
    "Alternate Phone",
]

_ALL_INLINE_LABELS = [
    label for _, labels in _VIATOR_INLINE_FIELDS for label in labels
] + _BOUNDARY_LABELS


def _strip_html_to_text(html: str) -> str:
    text = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</tr>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<td[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<th[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace(
        "&gt;", ">"
    )
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _escape_regex(value: str) -> str:
    return re.escape(value)


def _strip_urls_and_noise(text: str) -> str:
    text = re.sub(r"\[https?://[^\]]*\]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_value(raw: str) -> str | None:
    value = re.sub(r"\s+", " ", raw).strip()
    if len(value) < 1 or len(value) > 400:
        return None
    if re.search(r"=0A|=0D|=3D", value, re.IGNORECASE):
        return None
    if re.fullmatch(r"no|n/a|none|—|-", value, re.IGNORECASE):
        return None
    value = re.sub(r"send the customer a message\.?", "", value, flags=re.IGNORECASE).strip()
    return value or None


def _sanitize_airline(raw: str | None) -> str | None:
    if not raw:
        return None
    value = re.sub(r"\s+", " ", raw).strip()
    value = re.split(
        r"\s+(?:arrival|departure)\s+(?:time|flight|airline)\s*(?:no\.?|number)?\s*:",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    if re.search(r"\d{1,2}:\d{2}\s*(?:am|pm)?|\btime\b", value, re.IGNORECASE):
        return None
    value = value.strip(" ,;-")
    if not value or len(value) > 40:
        return None
    return _sanitize_value(value)


def _sanitize_flight_number(raw: str | None) -> str | None:
    if not raw:
        return None
    value = re.sub(r"\s+", " ", raw).strip()
    if re.search(r"\d{1,2}:\d{2}\s*(?:am|pm)?", value, re.IGNORECASE) or re.search(
        r"\btime\b", value, re.IGNORECASE
    ):
        return None
    compact = re.sub(r"\s+", "", value)
    if not re.fullmatch(r"[A-Za-z0-9-]{1,12}", compact):
        return None
    return _sanitize_value(compact)


def _sanitize_time_label(raw: str | None) -> str | None:
    if not raw:
        return None
    value = re.sub(r"\s+", " ", raw).strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}\s*(?:am|pm)?", value, re.IGNORECASE):
        return None
    return _sanitize_value(value)


def _extract_booking_section(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    start_match = re.search(r"Booking\s+Details|Booking\s+Reference\s*:", normalized, re.IGNORECASE)
    start = start_match.start() if start_match else 0
    section = normalized[start:]
    end_match = re.search(
        r"(?:^|\n)\s*(?:Have questions|Optional:\s*Acknowledge|You can go to our Help)",
        section,
        re.IGNORECASE | re.MULTILINE,
    )
    if end_match and end_match.start() > 0:
        section = section[: end_match.start()]
    return _strip_urls_and_noise(section.replace("\n", " "))


def _read_inline_label(section: str, label: str) -> str | None:
    others = sorted(
        [item for item in _ALL_INLINE_LABELS if item != label],
        key=len,
        reverse=True,
    )
    stop = "|".join(_escape_regex(item) for item in others) if others else "(?!)"
    pattern = rf"{_escape_regex(label)}\s*:\s*(.+?)(?=\s+(?:{stop})\s*:|$)"
    match = re.search(pattern, section, re.IGNORECASE | re.DOTALL)
    return _sanitize_value(match.group(1)) if match else None


def _extract_inline_fields(section: str) -> ViatorBookingDetails:
    fields: ViatorBookingDetails = {}
    for key, labels in _VIATOR_INLINE_FIELDS:
        for label in labels:
            value = _read_inline_label(section, label)
            if value and key not in fields:
                fields[key] = value  # type: ignore[literal-required]
    return fields


def _extract_alternate_phone(text: str) -> str | None:
    patterns = [
        r"\(Alternate\s+Phone\)\s*([A-Z]{0,3}\+?[\d\s().-]{8,24})",
        r"Alternate\s+Phone\s*:\s*([A-Z]{0,3}\+?[\d\s().-]{8,24})",
        r"Phone\s*:\s*([A-Z]{0,3}\+?[\d\s().-]{8,24})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            phone = normalize_phone_number(re.sub(r"\s+", " ", match.group(1)))
            if len(phone) >= 8:
                return phone
    return None


def _extract_embedded_leg(text: str, leg: str) -> dict[str, str | None]:
    prefix = leg
    out: dict[str, str | None] = {}
    airline = re.search(
        rf"\b{prefix}\s+airline\s*:\s*([A-Za-z0-9]{{2,12}})\b",
        text,
        re.IGNORECASE,
    )
    flight = re.search(
        rf"\b{prefix}\s+flight\s*(?:no\.?|number)?\s*:\s*([A-Za-z0-9]{{1,10}})\b",
        text,
        re.IGNORECASE,
    )
    time_value = None
    if leg in ("arrival", "departure"):
        # Fixed-width lookbehinds only (Python re rejects \s+ in lookbehind).
        time_match = re.search(
            rf"(?<!disembarkation )(?<!disembarkment )\b{prefix}\s+time\s*:\s*(\d{{1,2}}:\d{{2}}\s*(?:am|pm)?)\b",
            text,
            re.IGNORECASE,
        )
        time_value = time_match.group(1) if time_match else None
    if airline:
        out["airline"] = _sanitize_airline(airline.group(1))
    if flight:
        out["flightNo"] = _sanitize_flight_number(flight.group(1))
    if time_value:
        out["time"] = _sanitize_time_label(time_value)
    return out


def _apply_embedded_leg_from_pickup(fields: ViatorBookingDetails) -> None:
    raw = fields.get("pickupLocation")
    if not raw:
        return
    arrival = _extract_embedded_leg(raw, "arrival")
    departure = _extract_embedded_leg(raw, "departure")
    if not fields.get("arrivalAirline") and arrival.get("airline"):
        fields["arrivalAirline"] = arrival["airline"]
    if not fields.get("arrivalFlightNo") and arrival.get("flightNo"):
        fields["arrivalFlightNo"] = arrival["flightNo"]
    if not fields.get("arrivalTime") and arrival.get("time"):
        fields["arrivalTime"] = arrival["time"]
    if not fields.get("departureAirline") and departure.get("airline"):
        fields["departureAirline"] = departure["airline"]
    if not fields.get("departureFlightNo") and departure.get("flightNo"):
        fields["departureFlightNo"] = departure["flightNo"]
    if not fields.get("departureTime") and departure.get("time"):
        fields["departureTime"] = departure["time"]


def _normalize_flight_and_time_fields(fields: ViatorBookingDetails) -> None:
    fields["arrivalAirline"] = _sanitize_airline(fields.get("arrivalAirline"))
    fields["departureAirline"] = _sanitize_airline(fields.get("departureAirline"))
    fields["arrivalFlightNo"] = _sanitize_flight_number(fields.get("arrivalFlightNo"))
    fields["departureFlightNo"] = _sanitize_flight_number(fields.get("departureFlightNo"))
    fields["arrivalTime"] = _sanitize_time_label(fields.get("arrivalTime"))
    fields["departureTime"] = _sanitize_time_label(fields.get("departureTime"))
    fields["disembarkationTime"] = _sanitize_time_label(fields.get("disembarkationTime"))


def _clean_pickup_location_label(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw
    value = re.sub(r"\s+special\s+requirements\s*:.*", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s+boarding\s+time\s*:.*", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(
        r"\s+arrival\s+(?:flight|airline|time)\s*(?:no\.?|number)?\s*:.*",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()
    value = re.sub(
        r"\s+departure\s+(?:flight|airline|time)\s*(?:no\.?|number)?\s*:.*",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()
    value = re.sub(r"\s+disembark(?:ation|ment)\s+time\s*:.*", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(
        r"\s+(?:drop[\s-]*off(?:\s+(?:location(?:\s+name)?|point))?|destination|port\s+drop[\s-]*off)\s*:.*",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()
    value = re.sub(r"\(?alternate\s+phone\)?.*$", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\bphone\s*:.*", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\bUS\+?\d[\d\s().-]{7,}\b", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s{2,}", " ", value).strip()
    cleaned = _sanitize_value(value)
    if not cleaned:
        return None
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    if not parts:
        return None
    first = parts[0]
    second = parts[1] if len(parts) > 1 else None
    if second and first.lower() == second.lower():
        return _sanitize_value(first)
    if len(parts) > 2:
        return _sanitize_value(first)
    return _sanitize_value(cleaned)


def _clean_special_requirements(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw
    value = re.sub(r"^no\s*phone\s*:\s*", "", value, flags=re.IGNORECASE).strip()
    if re.match(r"^\(alternate phone\)", value, re.IGNORECASE):
        return None
    if re.search(r"phone\s*:", value, re.IGNORECASE):
        before_phone = re.split(r"\s*phone\s*:", value, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        value = before_phone if before_phone and not re.fullmatch(r"no", before_phone, re.IGNORECASE) else ""
    return _sanitize_value(value)


def _extract_from_text(text: str) -> ViatorBookingDetails:
    section = _extract_booking_section(text)
    fields = _extract_inline_fields(section)
    phone = _extract_alternate_phone(section) or _extract_alternate_phone(text)
    if phone:
        fields["phone"] = phone
    fields["specialRequirements"] = _clean_special_requirements(fields.get("specialRequirements"))
    _normalize_flight_and_time_fields(fields)
    _apply_embedded_leg_from_pickup(fields)
    cruise_ship = (fields.get("cruiseShipName") or "").strip()
    fields["cruiseShipName"] = _sanitize_value(cruise_ship) if cruise_ship else None
    fields["pickupLocation"] = _clean_pickup_location_label(fields.get("pickupLocation"))
    fields["dropoffLocation"] = _clean_pickup_location_label(fields.get("dropoffLocation"))
    if fields.get("productName"):
        fields["productName"] = re.sub(
            r"\s+Travel\s+Date\s*$",
            "",
            fields["productName"],
            flags=re.IGNORECASE,
        ).strip()
    product_code = normalize_viator_product_code(_read_inline_label(section, "Product Code"))
    if product_code:
        fields["productCode"] = product_code
    return fields


def parse_viator_email_body(raw_source: bytes | str) -> ViatorBookingDetails:
    source = raw_source if isinstance(raw_source, bytes) else raw_source.encode("utf-8", errors="replace")
    try:
        parsed = parse_from_bytes(source)
        text = (parsed.text or "").strip()
        if not text and parsed.text_html:
            html = parsed.text_html[0] if isinstance(parsed.text_html, list) else parsed.text_html
            text = _strip_html_to_text(str(html))
        if text:
            return _extract_from_text(text)
    except Exception:
        pass
    fallback = _strip_html_to_text(source.decode("utf-8", errors="replace"))
    return _extract_from_text(fallback)


def parse_viator_booking_reference_from_text(
    text: str,
    *,
    allow_test_marker: bool = False,
) -> str | None:
    section = _extract_booking_section(text)
    raw = _read_inline_label(section, "Booking Reference")
    if not raw:
        return None
    normalized = raw.strip().upper()
    if re.fullmatch(r"BR-\d+", normalized):
        return normalized
    if allow_test_marker and re.fullmatch(r"BR-TEST", normalized, re.IGNORECASE):
        return normalized
    return None


def parse_viator_booking_reference_from_body(
    raw_source: bytes | str,
    *,
    allow_test_marker: bool = False,
) -> str | None:
    source = raw_source if isinstance(raw_source, bytes) else raw_source.encode("utf-8", errors="replace")
    try:
        parsed = parse_from_bytes(source)
        text = (parsed.text or "").strip()
        if not text and parsed.text_html:
            html = parsed.text_html[0] if isinstance(parsed.text_html, list) else parsed.text_html
            text = _strip_html_to_text(str(html))
        if text:
            return parse_viator_booking_reference_from_text(text, allow_test_marker=allow_test_marker)
    except Exception:
        pass
    fallback = _strip_html_to_text(source.decode("utf-8", errors="replace"))
    return parse_viator_booking_reference_from_text(fallback, allow_test_marker=allow_test_marker)
