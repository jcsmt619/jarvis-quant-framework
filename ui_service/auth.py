from __future__ import annotations

import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthResult:
    allowed: bool
    code: str


class LocalSessionAuthorizer:
    """Memory-only local session boundary.

    Tokens are injected or generated at runtime. This class never logs,
    persists, prints, or derives provider/broker credentials.
    """

    def __init__(self, token: str | None = None) -> None:
        self._token = token or secrets.token_urlsafe(32)
        if not self._token or any(ch.isspace() for ch in self._token):
            raise ValueError("local session token must be a non-empty opaque value")

    def check(self, authorization_values: list[str] | None) -> AuthResult:
        if authorization_values is None or len(authorization_values) == 0:
            return AuthResult(False, "missing")
        if len(authorization_values) != 1:
            return AuthResult(False, "duplicated")
        header = authorization_values[0]
        if not header.startswith("Bearer "):
            return AuthResult(False, "malformed")
        candidate = header[7:]
        if not candidate or any(ch.isspace() for ch in candidate):
            return AuthResult(False, "malformed")
        if not secrets.compare_digest(candidate, self._token):
            return AuthResult(False, "invalid")
        return AuthResult(True, "authorized")
