from __future__ import annotations

import random

VIATOR_ALLOWED_PRODUCT_CODES = [
    "406570P1",
    "406570P2",
    "406570P4",
    "406570P6",
    "406570P7",
    "406570P9",
    "406570P10",
    "406570P13",
    "406570P14",
    "406570P15",
    "406570P19",
    "406570P20",
    "406570P22",
    "406570P23",
    "406570P26",
    "406570P28",
    "406570P32",
    "406570P34",
    "406570P40",
    "406570P42",
    "406570P52",
    "406570P54",
    "406570P3",
    "406570P16",
    "406570P21",
    "406570P35",
    "406570P39",
    "406570P56",
    "406570P57",
    "406570P60",
    "406570P62",
    "419333P4",
    "419333P8",
    "419333P11",
    "419333P15",
    "419333P18",
    "419333P19",
    "419333P23",
]

VIATOR_CITY_TO_CRUISE_PRODUCT_CODES = [
    "406570P62",
    "406570P57",
    "406570P56",
    "406570P39",
    "406570P35",
    "406570P21",
    "406570P16",
    "406570P3",
    "419333P25",
    "419333P23",
    "419333P18",
    "419333P12",
    "419333P7",
    "419333P32",
]


_ALLOWED_SET = frozenset(VIATOR_ALLOWED_PRODUCT_CODES)
_CITY_TO_CRUISE_SET = frozenset(VIATOR_CITY_TO_CRUISE_PRODUCT_CODES)


def normalize_viator_product_code(raw: str | None) -> str | None:
    if not raw:
        return None
    code = raw.strip().upper().replace(" ", "")
    if not code or not code.isalnum():
        return None
    return code


def is_allowed_viator_product_code(code: str | None) -> bool:
    normalized = normalize_viator_product_code(code)
    return bool(normalized and normalized in _ALLOWED_SET)


def is_city_to_cruise_product_code(code: str | None) -> bool:
    normalized = normalize_viator_product_code(code)
    return bool(normalized and normalized in _CITY_TO_CRUISE_SET)


def pick_random_allowed_viator_product_code() -> str:
    return random.choice(VIATOR_ALLOWED_PRODUCT_CODES)
