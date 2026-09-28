# Paystream

A small Python ledger used as a local case workspace.

- `POST /tokens` issues a session token.
- `GET /sessions/validate` accepts or rejects that token.
- `GET /users/{id}/activity` returns the user's transactions.

`Ledger.transactions_for` is one round trip per account. `transactions_for_accounts` reads a set of accounts in one round trip.
