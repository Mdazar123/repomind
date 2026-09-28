"""In-memory ledger. One call counts as one round trip."""

from __future__ import annotations


class Ledger:
    def __init__(self, accounts: list[dict], transactions: list[dict]) -> None:
        self._accounts = list(accounts)
        self._transactions = list(transactions)
        self.transaction_calls = 0

    async def accounts_for(self, user_id: str) -> list[dict]:
        return [row for row in self._accounts if row["user_id"] == user_id]

    async def transactions_for(self, account_id: str) -> list[dict]:
        self.transaction_calls += 1
        return [row for row in self._transactions if row["account_id"] == account_id]

    async def transactions_for_accounts(self, account_ids: list[str]) -> list[dict]:
        self.transaction_calls += 1
        wanted = set(account_ids)
        return [row for row in self._transactions if row["account_id"] in wanted]
