"""HTTP-shaped handlers. Comments mark the route each function serves."""

from __future__ import annotations

from paystream.activity import load_user_activity
from paystream.auth.tokens import issue_token, token_is_active


# route: POST /tokens
def post_tokens(subject: str, now: float | None = None) -> dict:
    return issue_token(subject, now=now)


# route: GET /sessions/validate
def get_session(token: dict, now: float | None = None) -> tuple[int, dict]:
    if not token_is_active(token, now=now):
        return 401, {"detail": "token rejected"}
    return 200, {"ok": True, "sub": token.get("sub")}


# route: GET /users/{user_id}/activity
async def get_activity(user_id: str, ledger) -> tuple[int, dict]:
    rows = await load_user_activity(user_id, ledger)
    return 200, {"transactions": rows}
