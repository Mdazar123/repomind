"""Frozen case statements. The wording is part of the critic's behavior."""

from __future__ import annotations

TOKEN_CASE = (
    "Freshly issued session tokens are rejected with 401. "
    "On-call notes also mention latency — confirm which fault actually explains the rejections."
)

LATENCY_CASE = (
    "Account activity got slow once users started holding several accounts. "
    "Notes also mention 401s — confirm which fault explains the slowdown."
)
