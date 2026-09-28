# RepoMind

RepoMind investigates a Python repository **on your machine**. A security agent and a performance agent file only what they can point at. A critic rejects a theory that does not explain the symptom. A patch counts only when a targeted test fails before the edit and passes after it.

The repository is not uploaded. This site shows one finished case from the bundled Paystream service.

## Install

The name `repomind` on PyPI already belongs to a different project. This package is `repomind-local`. The command is still `repomind`.

From a checkout:

```bash
pip install -e .
repomind demo
```

After the package is published:

```bash
pip install repomind-local
repomind demo
```

## Commands

```bash
repomind doctor
repomind demo
repomind explain "Fresh tokens are rejected with 401" .
repomind scan .
repomind fix 1
```

`fix` prints the diff and asks before it writes. Pass `--yes` to apply it in a script.

## What `repomind demo` shows

Paystream is a small ledger with two real defects and tests that fail:

- `token_is_active` compares a unix-second expiry with `now * 1000`, so a fresh token looks expired.
- `load_user_activity` calls `transactions_for` once per account even though `transactions_for_accounts` exists.

On-call notes mention latency first. For the token case, the hypothesis agent follows that lead, the critic rejects it, and the clock-unit fix is the one that turns `tests/test_tokens.py` green.

## Optional local model

Findings do not come from a hosted model. If you want the case note rewritten locally:

```bash
pip install "repomind-local[model]"
repomind model download --size 1.5b
```

That downloads Qwen2.5-Coder 1.5B Q4 from Hugging Face into `~/.cache/repomind/models`. `--size 7b` is the larger option. No API key.

## Layout

```text
src/repomind/          CLI, LangGraph workflow, detectors, fixes, sandbox proof
src/repomind/fixtures/paystream
web/                   Next.js case file
tests/                 The token case and the latency case must prove their patches
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Site

```bash
cd web
npm install
npm run dev
```

The dev server listens on port 8742.
