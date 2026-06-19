from __future__ import annotations

import os

DEFAULT_LOOKBACK_HOURS = 6


def resolve_lookback_hours() -> int:
    raw = (os.getenv("VIATOR_INBOX_LOOKBACK_HOURS") or "").strip()
    if not raw:
        return DEFAULT_LOOKBACK_HOURS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_LOOKBACK_HOURS
    if parsed <= 0:
        return DEFAULT_LOOKBACK_HOURS
    return min(parsed, 168)


VIATOR_INBOX_LOOKBACK_HOURS = resolve_lookback_hours()
