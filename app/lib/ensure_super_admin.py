from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import bcrypt
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

SALT_ROUNDS = 10


@dataclass(frozen=True)
class SuperAdminBootstrap:
    email: str
    password: str
    phone: str
    full_name: str


EnsureSuperAdminResult = dict[str, str]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=SALT_ROUNDS),
    ).decode("utf-8")


def read_super_admin_bootstrap_from_env() -> SuperAdminBootstrap | None:
    email = (os.getenv("SUPER_ADMIN_EMAIL") or "").strip().lower()
    password = (os.getenv("SUPER_ADMIN_PASSWORD") or "").strip()
    phone = (os.getenv("SUPER_ADMIN_PHONE") or "").strip()
    full_name = (os.getenv("SUPER_ADMIN_FULL_NAME") or "").strip()

    any_set = bool(email or password or phone or full_name)
    if not any_set:
        return None

    if not email or not password or not phone or not full_name:
        raise ValueError(
            "Set all of SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, "
            "SUPER_ADMIN_PHONE, SUPER_ADMIN_FULL_NAME (or leave all unset to skip)."
        )

    if len(password) < 8:
        raise ValueError("SUPER_ADMIN_PASSWORD must be at least 8 characters.")

    return SuperAdminBootstrap(
        email=email,
        password=password,
        phone=phone,
        full_name=full_name,
    )


def format_ensure_super_admin_error(error: Exception) -> str:
    if isinstance(error, IntegrityError):
        return "Unique constraint failed. Email and phone must be unused."
    return str(error)


def ensure_super_admin_from_env(
    conn: Connection,
    bootstrap: SuperAdminBootstrap,
) -> EnsureSuperAdminResult:
    existing = conn.execute(
        text(
            """
            SELECT id, email, is_admin, is_super_admin
            FROM `User`
            WHERE email = :email
            LIMIT 1
            """
        ),
        {"email": bootstrap.email},
    ).mappings().first()

    if existing:
        if not existing["is_admin"]:
            return {
                "status": "error",
                "message": (
                    f"User {bootstrap.email} exists but is not a staff admin "
                    "(is_admin is false)."
                ),
            }
        if not existing["is_super_admin"]:
            conn.execute(
                text("UPDATE `User` SET is_super_admin = 1 WHERE id = :id"),
                {"id": existing["id"]},
            )
            conn.commit()
            return {"status": "promoted"}
        return {"status": "exists"}

    driver = conn.execute(
        text("SELECT id FROM `Driver` WHERE email = :email LIMIT 1"),
        {"email": bootstrap.email},
    ).first()
    if driver:
        return {
            "status": "error",
            "message": (
                f"Email {bootstrap.email} is already used by a driver; "
                "choose another SUPER_ADMIN_EMAIL."
            ),
        }

    phone_user = conn.execute(
        text("SELECT email FROM `User` WHERE phone = :phone LIMIT 1"),
        {"phone": bootstrap.phone},
    ).mappings().first()
    if phone_user:
        return {
            "status": "error",
            "message": f"SUPER_ADMIN_PHONE is already used by staff user {phone_user['email']}.",
        }

    user_id = str(uuid.uuid4())
    conn.execute(
        text(
            """
            INSERT INTO `User` (
                id, fullName, email, phone, password,
                is_admin, is_super_admin, token_version, createdAt
            ) VALUES (
                :id, :full_name, :email, :phone, :password,
                1, 1, 0, NOW(3)
            )
            """
        ),
        {
            "id": user_id,
            "full_name": bootstrap.full_name,
            "email": bootstrap.email,
            "phone": bootstrap.phone,
            "password": hash_password(bootstrap.password),
        },
    )
    conn.commit()
    return {"status": "created", "user_id": user_id}
