from __future__ import annotations

TRASH_SUFFIX = "#trash-"


def normalize_booking_reference(booking_reference: str) -> str:
    trimmed = booking_reference.strip()
    trash_idx = trimmed.lower().find(TRASH_SUFFIX)
    if trash_idx > 0:
        return trimmed[:trash_idx].upper() + trimmed[trash_idx:]
    return trimmed.upper()


def canonical_booking_reference(booking_reference: str) -> str:
    """Original booking ref without any trash suffix, uppercased."""
    trimmed = booking_reference.strip()
    trash_idx = trimmed.lower().find(TRASH_SUFFIX)
    if trash_idx > 0:
        return trimmed[:trash_idx].upper()
    return trimmed.upper()


def booking_reference_trash_like_pattern(canonical_ref: str) -> str:
    """SQL LIKE pattern matching any trashed rename of a canonical reference."""
    return f"{escape_mysql_like_pattern(canonical_ref)}{TRASH_SUFFIX}%"


def display_booking_reference(booking_reference: str) -> str:
    trash_idx = booking_reference.lower().find(TRASH_SUFFIX)
    if trash_idx > 0:
        return booking_reference[:trash_idx]
    return booking_reference


def trashed_booking_reference(booking_reference: str, booking_uuid: str) -> str:
    trimmed = booking_reference.strip()
    if TRASH_SUFFIX in trimmed.lower():
        return normalize_booking_reference(trimmed)
    return f"{normalize_booking_reference(trimmed)}{TRASH_SUFFIX}{booking_uuid}"


def booking_reference_search_needle(raw_query: str) -> str | None:
    needle = raw_query.strip().upper()
    return needle if needle else None


def escape_mysql_like_pattern(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def booking_reference_search_like_pattern(raw_query: str) -> str | None:
    needle = booking_reference_search_needle(raw_query)
    if not needle:
        return None
    return f"%{escape_mysql_like_pattern(needle)}%"


def viator_references_for_booking(booking_reference: str) -> list[str]:
    refs = {
        booking_reference,
        normalize_booking_reference(booking_reference),
    }
    trash_idx = booking_reference.lower().find(TRASH_SUFFIX)
    if trash_idx > 0:
        refs.add(normalize_booking_reference(booking_reference[:trash_idx]))
    return list(refs)
