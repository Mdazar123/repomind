import asyncio

from paystream.activity import load_user_activity
from paystream.ledger import Ledger


def _ledger() -> Ledger:
    accounts = [
        {"id": "a1", "user_id": "u1"},
        {"id": "a2", "user_id": "u1"},
        {"id": "a3", "user_id": "u1"},
    ]
    transactions = [
        {"id": f"t{index}", "account_id": account_id, "amount": index}
        for index, account_id in enumerate(["a1", "a1", "a2", "a3", "a3", "a3"])
    ]
    return Ledger(accounts, transactions)


def test_activity_uses_one_ledger_read():
    ledger = _ledger()
    rows = asyncio.run(load_user_activity("u1", ledger))
    assert len(rows) == 6
    assert ledger.transaction_calls == 1
