"""Track failed Prices passcode attempts with escalating lockouts.

State is on disk so lockouts survive API reloads and can be inspected/cleared
from a CLI script.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

MAX_FAILED_ATTEMPTS = 3
LOCKOUT_STEP_SECONDS = 5 * 60  # +5 minutes per lockout cycle
UNLOCK_SESSION_SECONDS = 30 * 60


def pricing_passcode_attempts_file() -> Path:
    override = (os.getenv("PRICING_PASSCODE_ATTEMPTS_FILE") or "").strip()
    if override:
        return Path(override)
    root = Path(__file__).resolve().parents[3]  # server-side/
    return root / ".data" / "pricing_passcode_attempts.json"


@dataclass
class _AttemptState:
    failures: int = 0
    lockouts: int = 0
    locked_until: float = 0.0
    unlocked_until: float = 0.0


class PricingPasscodeAttemptTracker:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._path = path or pricing_passcode_attempts_file()

    def _key(self, principal_id: str) -> str:
        return (principal_id or "").strip() or "anonymous"

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
                unlocked_until=float(value.get("unlocked_until") or 0.0),
            )
        return out

    def _save(self, states: dict[str, _AttemptState]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            key: {
                "failures": state.failures,
                "lockouts": state.lockouts,
                "locked_until": state.locked_until,
                "unlocked_until": state.unlocked_until,
            }
            for key, state in states.items()
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path)

    def _status_from_state(
        self, state: _AttemptState | None, now: float
    ) -> dict[str, float | int | bool]:
        if not state:
            return {
                "locked": False,
                "failures": 0,
                "lockouts": 0,
                "remaining_seconds": 0,
                "unlocked": False,
                "attempts_remaining": MAX_FAILED_ATTEMPTS,
            }
        remaining = max(0, int(state.locked_until - now))
        unlocked = state.unlocked_until > now
        attempts_remaining = (
            0 if remaining > 0 else max(0, MAX_FAILED_ATTEMPTS - state.failures)
        )
        return {
            "locked": remaining > 0,
            "failures": state.failures,
            "lockouts": state.lockouts,
            "remaining_seconds": remaining,
            "unlocked": unlocked,
            "attempts_remaining": attempts_remaining,
        }

    def status(self, principal_id: str) -> dict[str, float | int | bool]:
        key = self._key(principal_id)
        now = time.time()
        with self._lock:
            return self._status_from_state(self._load().get(key), now)

    def begin_gate_visit(self, principal_id: str) -> dict[str, float | int | bool]:
        """Leaving and re-opening the gate starts a fresh try (3 attempts, no lockout)."""
        key = self._key(principal_id)
        now = time.time()
        with self._lock:
            states = self._load()
            state = states.get(key) or _AttemptState()
            state.failures = 0
            state.lockouts = 0
            state.locked_until = 0.0
            state.unlocked_until = 0.0
            states[key] = state
            self._save(states)
            return self._status_from_state(state, now)

    def assert_not_locked(self, principal_id: str) -> None:
        key = self._key(principal_id)
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
                    f"Too many failed passcode attempts. "
                    f"Try again in about {minutes} minute{'s' if minutes != 1 else ''}."
                ),
                headers={"Retry-After": str(max(1, remaining))},
            )

    def assert_unlocked(self, principal_id: str) -> None:
        key = self._key(principal_id)
        now = time.time()
        with self._lock:
            state = self._load().get(key)
            if state and state.unlocked_until > now:
                return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pricing passcode required",
        )

    def record_failure(self, principal_id: str) -> dict[str, float | int | bool]:
        key = self._key(principal_id)
        now = time.time()
        with self._lock:
            states = self._load()
            state = states.get(key)
            if state is None:
                state = _AttemptState()
                states[key] = state

            if state.locked_until > now:
                self._save(states)
                remaining = int(state.locked_until - now)
                minutes = max(1, (remaining + 59) // 60)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Too many failed passcode attempts. "
                        f"Try again in about {minutes} minute{'s' if minutes != 1 else ''}."
                    ),
                    headers={"Retry-After": str(max(1, remaining))},
                )

            if state.locked_until and state.locked_until <= now:
                state.failures = 0
                state.locked_until = 0.0

            state.failures += 1
            state.unlocked_until = 0.0
            if state.failures < MAX_FAILED_ATTEMPTS:
                self._save(states)
                return {
                    "locked": False,
                    "failures": state.failures,
                    "lockouts": state.lockouts,
                    "remaining_seconds": 0,
                    "unlocked": False,
                    "attempts_remaining": MAX_FAILED_ATTEMPTS - state.failures,
                }

            state.lockouts += 1
            state.failures = 0
            lock_seconds = state.lockouts * LOCKOUT_STEP_SECONDS
            state.locked_until = now + lock_seconds
            self._save(states)
            minutes = lock_seconds // 60
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many failed passcode attempts. "
                    f"Locked for {minutes} minute{'s' if minutes != 1 else ''}."
                ),
                headers={"Retry-After": str(lock_seconds)},
            )

    def mark_unlocked(self, principal_id: str) -> dict[str, float | int | bool]:
        key = self._key(principal_id)
        now = time.time()
        with self._lock:
            states = self._load()
            state = states.get(key) or _AttemptState()
            state.failures = 0
            state.locked_until = 0.0
            state.unlocked_until = now + UNLOCK_SESSION_SECONDS
            states[key] = state
            self._save(states)
            return {
                "locked": False,
                "failures": 0,
                "lockouts": state.lockouts,
                "remaining_seconds": 0,
                "unlocked": True,
                "attempts_remaining": MAX_FAILED_ATTEMPTS,
                "unlocked_for_seconds": UNLOCK_SESSION_SECONDS,
            }

    def clear_unlock(self, principal_id: str) -> None:
        key = self._key(principal_id)
        with self._lock:
            states = self._load()
            state = states.get(key)
            if not state:
                return
            state.unlocked_until = 0.0
            self._save(states)

    def clear(self, principal_id: str) -> bool:
        key = self._key(principal_id)
        with self._lock:
            states = self._load()
            existed = key in states
            states.pop(key, None)
            self._save(states)
            return existed


pricing_passcode_attempts = PricingPasscodeAttemptTracker()
