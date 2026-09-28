"""Load every transaction for a user's accounts."""

from __future__ import annotations


async def load_user_activity(user_id: str, ledger) -> list[dict]:
    accounts = await ledger.accounts_for(user_id)
    rows: list[dict] = []
    for account in accounts:
        rows.extend(await ledger.transactions_for(account["id"]))
    return rows
