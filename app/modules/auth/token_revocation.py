from __future__ import annotations

import time


class TokenRevocationService:
    """In-memory revoked access-token jti values until their JWT exp."""

    def __init__(self) -> None:
        self._revoked_jti_until_exp: dict[str, int] = {}

    def revoke_until(self, jti: str, exp_unix_sec: int) -> None:
        self._revoked_jti_until_exp[jti] = exp_unix_sec
        self._prune_expired()

    def is_revoked(self, jti: str | None) -> bool:
        if not jti:
            return False
        exp = self._revoked_jti_until_exp.get(jti)
        if exp is None:
            return False
        now = int(time.time())
        if now >= exp:
            self._revoked_jti_until_exp.pop(jti, None)
            return False
        return True

    def _prune_expired(self) -> None:
        now = int(time.time())
        expired = [jti for jti, exp in self._revoked_jti_until_exp.items() if now >= exp]
        for jti in expired:
            self._revoked_jti_until_exp.pop(jti, None)


token_revocation = TokenRevocationService()
