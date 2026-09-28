"""Map a case statement and on-call notes onto fault categories."""

from __future__ import annotations

AUTH_WORDS = (
    "token",
    "tokens",
    "401",
    "unauthorized",
    "login",
    "session",
    "jwt",
    "rejected",
)
LATENCY_WORDS = (
    "slow",
    "latency",
    "n+1",
    "roundtrip",
    "round-trip",
    "performance",
    "timeout",
)


def _earliest(text: str) -> str | None:
    lowered = text.lower()
    hits: list[tuple[int, str]] = []
    for word in AUTH_WORDS:
        index = lowered.find(word)
        if index >= 0:
            hits.append((index, "auth"))
    for word in LATENCY_WORDS:
        index = lowered.find(word)
        if index >= 0:
            hits.append((index, "latency"))
    if not hits:
        return None
    hits.sort(key=lambda item: item[0])
    return hits[0][1]


def primary_symptom(problem: str) -> str:
    """Category the case statement itself leads with, ignoring later asides."""
    return _earliest(problem) or "general"


def note_bias(notes: str) -> str | None:
    """Category mentioned first in on-call notes. Empty notes have no bias."""
    if not notes.strip():
        return None
    return _earliest(notes)


def choose_hypothesis(
    findings: list[dict],
    problem: str,
    notes: str,
    round_index: int,
    dismissed: set[str],
) -> dict | None:
    pool = [finding for finding in findings if finding["id"] not in dismissed]
    if not pool:
        return None
    if round_index == 0:
        bias = note_bias(notes)
        biased = [finding for finding in pool if finding["category"] == bias]
        if biased:
            return max(biased, key=lambda finding: finding["confidence"])
    symptom = primary_symptom(problem)
    def score(finding: dict) -> float:
        if symptom == "general":
            alignment = 0.2
        elif finding["category"] == symptom:
            alignment = 2.0
        else:
            alignment = 0.0
        return alignment + float(finding["confidence"])
    return max(pool, key=score)


def symptom_conflict(problem: str, category: str) -> str | None:
    symptom = primary_symptom(problem)
    if symptom == "general" or symptom == category:
        return None
    if symptom == "auth" and category == "latency":
        return (
            "The case leads with rejected tokens. A sequential ledger read can "
            "make a request slow. It cannot make a freshly issued token look expired."
        )
    if symptom == "latency" and category == "auth":
        return (
            "The case leads with a slow activity read. A clock-unit mistake can "
            "reject a token. It does not add a query per account."
        )
    return None
