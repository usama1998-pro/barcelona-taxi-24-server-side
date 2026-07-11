"""Track failed password sign-in attempts and escalating lockouts.

State is stored on disk so a CLI script can clear a lockout while the API
process is still running (in-memory alone would not be visible to another process).
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_STEP_SECONDS = 15 * 60  # +15 minutes per lockout cycle


def login_attempts_file() -> Path:
    override = (os.getenv("LOGIN_ATTEMPTS_FILE") or "").strip()
    if override:
        return Path(override)
    root = Path(__file__).resolve().parents[3]  # server-side/
    return root / ".data" / "login_attempts.json"


@dataclass
class _AttemptState:
    failures: int = 0
    lockouts: int = 0
    locked_until: float = 0.0  # wall-clock (time.time)


class LoginAttemptTracker:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._path = path or login_attempts_file()

    def _key(self, email: str) -> str:
        return email.strip().lower()

    def _load(self) -> dict[str, _AttemptState]:
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        out: dict[str, _AttemptState] = {}
        for key, value in data.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            out[key] = _AttemptState(
                failures=int(value.get("failures") or 0),
                lockouts=int(value.get("lockouts") or 0),
                locked_until=float(value.get("locked_until") or 0.0),
            )
        return out

    def _save(self, states: dict[str, _AttemptState]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            key: {
                "failures": state.failures,
                "lockouts": state.lockouts,
                "locked_until": state.locked_until,
            }
            for key, state in states.items()
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path)

    def status(self, email: str) -> dict[str, float | int | bool]:
        """Return lockout info for an email (for CLI / ops)."""
        key = self._key(email)
        now = time.time()
        with self._lock:
            state = self._load().get(key)
            if not state:
                return {"email": key, "locked": False, "failures": 0, "lockouts": 0, "remaining_seconds": 0}
            remaining = max(0, int(state.locked_until - now))
            return {
                "email": key,
                "locked": remaining > 0,
                "failures": state.failures,
                "lockouts": state.lockouts,
                "remaining_seconds": remaining,
            }

    def assert_not_locked(self, email: str) -> None:
        key = self._key(email)
        now = time.time()
        with self._lock:
            state = self._load().get(key)
            if not state or state.locked_until <= now:
                return
            remaining = int(state.locked_until - now)
            minutes = max(1, (remaining + 59) // 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many failed sign-in attempts. "
                    f"Try again in about {minutes} minute{'s' if minutes != 1 else ''}."
                ),
                headers={"Retry-After": str(max(1, remaining))},
            )

    def record_failure(self, email: str) -> None:
        key = self._key(email)
        now = time.time()
        with self._lock:
            states = self._load()
            state = states.get(key)
            if state is None:
                state = _AttemptState()
                states[key] = state

            if state.locked_until > now:
                self._save(states)
                return

            # Lock expired: keep lockout count for escalation, reset failure streak.
            if state.locked_until and state.locked_until <= now:
                state.failures = 0
                state.locked_until = 0.0

            state.failures += 1
            if state.failures < MAX_FAILED_ATTEMPTS:
                self._save(states)
                return

            state.lockouts += 1
            state.failures = 0
            lock_seconds = state.lockouts * LOCKOUT_STEP_SECONDS
            state.locked_until = now + lock_seconds
            self._save(states)
            minutes = lock_seconds // 60
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many failed sign-in attempts. "
                    f"Account locked for {minutes} minutes."
                ),
                headers={"Retry-After": str(lock_seconds)},
            )

    def clear(self, email: str) -> bool:
        """Clear failures + lockout for one email. Returns True if an entry existed."""
        key = self._key(email)
        with self._lock:
            states = self._load()
            existed = key in states
            states.pop(key, None)
            self._save(states)
            return existed

    def clear_all(self) -> int:
        """Clear every tracked email. Returns how many entries were removed."""
        with self._lock:
            states = self._load()
            count = len(states)
            self._save({})
            return count

    def list_locked(self) -> list[dict[str, float | int | str | bool]]:
        now = time.time()
        with self._lock:
            states = self._load()
            rows: list[dict[str, float | int | str | bool]] = []
            for key, state in sorted(states.items()):
                remaining = max(0, int(state.locked_until - now))
                if remaining <= 0 and state.failures <= 0:
                    continue
                rows.append(
                    {
                        "email": key,
                        "locked": remaining > 0,
                        "failures": state.failures,
                        "lockouts": state.lockouts,
                        "remaining_seconds": remaining,
                    }
                )
            return rows


login_attempts = LoginAttemptTracker()
