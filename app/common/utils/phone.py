from __future__ import annotations

import re


def normalize_phone_number(phone: str) -> str:
    s = phone.strip()
    if not s:
        return s

    s = re.sub(r"^[A-Z]{2,3}(?=\s*\+)", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"^[A-Z]{2,3}(?=\s*\d)", "", s, flags=re.IGNORECASE).strip()

    plus_idx = s.find("+")
    if plus_idx > 0:
        prefix = s[:plus_idx].strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z\s-]*", prefix) and not re.search(r"\d", prefix):
            s = s[plus_idx:].strip()

    return re.sub(r"\s+", " ", s).strip()
