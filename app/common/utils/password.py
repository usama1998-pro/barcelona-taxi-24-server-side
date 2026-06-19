from __future__ import annotations

from typing import Any

import bcrypt

SALT_ROUNDS = 10


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(
        plain.encode("utf-8"),
        bcrypt.gensalt(rounds=SALT_ROUNDS),
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def without_password(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "password"}
