"""Issue and check Paystream session tokens."""

from __future__ import annotations

import time


def issue_token(subject: str, ttl_seconds: int = 3600, now: float | None = None) -> dict:
    issued = now if now is not None else time.time()
    return {
        "sub": subject,
        "iat": int(issued),
        "exp": int(issued) + ttl_seconds,
    }


def token_is_active(token: dict, now: float | None = None) -> bool:
    now_s = now if now is not None else time.time()
    return token["exp"] > now_s * 1000
