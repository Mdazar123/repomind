# RepoMind — Project Overview

RepoMind is a local command-line tool that investigates a Python repository, names the line that causes a problem, and proposes a fix. A fix is marked **proven** only when a related test fails before the change and passes after it.

| | |
|---|---|
| Install | `pip install repomind-local` (the command is `repomind`) |
| Package | https://pypi.org/project/repomind-local/ |
| Source | https://github.com/Mdazar123/repomind |
| Live case | https://mdazar123.github.io/repomind/ |
| Version | 0.3.2 |
| Author | Md Azhar |

---

## 1. The problem it solves

Most AI code tools read a repository and return an answer. The developer then has to decide whether that answer is correct. Three problems keep coming back:

1. **Answers without evidence.** A tool says “the login bug is probably in auth” and does not point to a line.
2. **Plausible but wrong causes.** A slow query is real, but it cannot explain why a fresh token is rejected with a 401. Many tools do not check whether a finding explains the reported symptom.
3. **Unverified fixes.** A suggested patch looks reasonable, but nobody ran the test that would show it works.

There is also a privacy issue. Private company code often cannot be uploaded to a hosted model.

RepoMind addresses all four:

- Every finding cites a **file and a line**.
- A **critic** rejects a cause that does not match the question.
- A patch is **proven** only by a test that goes from red to green.
- Everything runs **on the developer’s machine**. No source code is uploaded, and no paid API key is required.

---

## 2. What it does, from the user’s side

```bash
pip install repomind-local
repomind demo                              # the bundled Paystream case
repomind scan .                            # list problems in a Python project
repomind explain "Why does login fail?" .  # investigate one symptom
repomind fix 1                             # show a patch, ask before writing
repomind doctor                            # check the local tools
```

`fix` prints the diff and asks `Apply this patch? [y/N]`. Nothing is written without confirmation.

### Example: the Paystream case

Paystream is a small ledger service bundled with RepoMind. It contains two real defects, each with a failing test:

- `token_is_active` compares an expiry in seconds with `now * 1000`, so every fresh token looks expired.
- `load_user_activity` reads transactions once per account, even though a batch method already exists.

The on-call notes mention latency first. That makes the case a trap: a tool that follows the notes will blame the slow loop.

`repomind demo` produces this investigation:

1. The performance agent files the slow loop. The security agent files the clock-unit bug.
2. The hypothesis agent follows the notes and picks the slow loop.
3. The critic rejects it: a slow read can make a request slow, but it cannot make a fresh token look expired.
4. The hypothesis agent picks again from the question and selects `tokens.py:19`.
5. The critic re-reads that line and accepts it.
6. The fix agent removes `* 1000`.
7. The proof agent runs `tests/test_tokens.py` in two temporary copies. It fails on the original and passes on the patched copy.

Result: **PROVEN**. The original files are not modified.

---

## 3. Architecture

```text
Developer machine
│
├── repomind (Typer CLI)
│      │
│      ▼
│   LangGraph StateGraph
│      │
│      ├── Recon ──────────────┐
│      │                        │
│      │   ┌────────────────────┴────────────┐
│      │   ▼                                 ▼
│      │ Security agent            Performance agent     (run in parallel)
│      │   └────────────────────┬────────────┘
│      │                        ▼
│      │                   Hypothesis
│      │                        ▼
│      │                     Critic ──rejects──► Hypothesis (one retry)
│      │                        │ accepts
│      │                        ▼
│      │                       Fix ──no safe patch──► Publish
│      │                        │
│      │                        ▼
│      │                      Proof  (temporary copies + pytest)
│      │                        ▼
│      │                     Publish  (case report + .repomind/latest.json)
│      │
│      └── Rich terminal case file
│
└── Next.js site (static) — shows the Paystream case, deployed on GitHub Pages
```

### Technology

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | The tool analyzes Python, so it is written in Python |
| Orchestration | LangGraph `StateGraph` | Parallel agents, a shared state, and a conditional retry loop |
| CLI | Typer + Rich | Typed commands and a readable terminal report |
| Code analysis | Python `ast` | Exact line numbers and structural patches, not text guesses |
| Extra lint rules | Ruff | Undefined names, unsafe calls, and async rules |
| Proof | pytest in temporary copies | The real project is never changed during proof |
| Packaging | setuptools, `pyproject.toml`, PyPI | `pip install repomind-local` |
| Site | Next.js, TypeScript, Tailwind, shadcn/ui | Static case file |
| CI/CD | GitHub Actions | Tests on every push, and the site redeploys to GitHub Pages |

### Repository layout

```text
src/repomind/
  cli.py            Commands: doctor, scan, explain, demo, fix, model download
  workflow.py       The LangGraph graph and the seven agent nodes
  render.py         Terminal case file
  cases.py          The Paystream case statements
  model.py          Optional local Qwen model download and loading
  analysis/
    index.py        Reads files, functions, routes, and tests
    detectors.py    Token-clock and loop/batch detectors
    checks.py       Security, async, FastAPI, and reliability checks
    search.py       Finds functions that match a question
    symptoms.py     Chooses a cause and decides whether it matches the question
    fixes.py        Structural patches for the supported patterns
    proof.py        Test selection and before/after pytest runs
  fixtures/paystream/   The bundled demo service and its tests
tests/              RepoMind’s own tests
web/                Next.js case site
.github/workflows/  CI and GitHub Pages
```

The Python package is about 2,400 lines across 13 modules. RepoMind has 12 automated tests, and all pass in CI.

---

## 4. The agents in detail

RepoMind has seven agents. Each is a LangGraph node. They share one state object: the repository path, the question, the code index, the findings, the rejected theories, the current theory, the critic’s verdicts, the patch, the proof, and a log of what each agent wrote.

A final `publish` node assembles the report. It is bookkeeping, not an investigating agent.

### 4.1 Recon

**Role:** map the repository before anyone forms a theory.

- Walks the project and skips `.git`, virtual environments, `node_modules`, and build output.
- Parses every Python file with `ast`. It records functions, async functions, routes, call sites, and tests.
- Reads `ops/incident_notes.md` if the project has one. The notes are treated as a lead, not as evidence.
- Runs every detector and Ruff once. It sorts the findings by confidence and keeps the top 30.
- If there is a question, it keeps up to five functions whose **names** match its words. Common words such as “why”, “does”, and “fail” are ignored.

**Output:** the code index, the full finding catalog, and a log entry such as “Indexed 11 files, 14 functions, 3 tests.”

### 4.2 Security agent

**Role:** file correctness and security problems.

It takes every non-performance finding from the catalog:

- Hardcoded secrets such as `password = "..."`
- `subprocess` with `shell=True`
- SQL built with f-strings, `%`, `+`, or `.format()`
- JWT decoding with signature verification turned off, or with the `none` algorithm allowed
- Token expiry compared in the wrong unit
- FastAPI routes with no `response_model`
- `Depends(get_db())` instead of `Depends(get_db)`, and a `get_*` default with no `Depends`
- Undefined names, bare `except`, and `except Exception: pass`
- `open()` or a session that is never closed
- External calls with no retry

### 4.3 Performance agent

**Role:** file problems that make code slow or stall.

- A blocking call such as `time.sleep` or `requests.get` inside an `async` function
- An async FastAPI route that calls blocking code
- An `await` inside a loop
- A database call such as `execute` or `find_one` inside a loop
- A per-item call when a batch method already exists, for example `transactions_for` in a loop when `transactions_for_accounts` is defined
- An HTTP call with no `timeout`

Security and Performance run **in parallel** after Recon. LangGraph merges their findings into one list before the hypothesis step.

### 4.4 Hypothesis

**Role:** choose one cause to test.

- **First round, with notes:** if the incident notes lead with a category, such as latency, it picks the strongest finding in that category. This models a real on-call engineer following the first clue.
- **Later rounds, or with no notes:** it scores each finding by whether its category matches the question, plus its confidence.
- It never re-picks a theory the critic already rejected.

This agent is allowed to be wrong. The critic is what makes the answer trustworthy.

### 4.5 Critic

**Role:** reject any cause that is not supported.

It runs three checks, in order:

1. **Evidence check.** Re-read the cited line from disk. If the file changed or the line does not match, reject.
2. **Relevance check.** If the question is about “login”, the finding’s title, file, function, or line must mention “login”. Otherwise reject: “The question is about login. This line does not mention that, so it cannot be the cause.”
3. **Symptom check.** A latency finding cannot explain a rejected token. An auth finding cannot explain a slow query per account.

If it rejects, the theory is dismissed and the graph routes back to Hypothesis. After two rounds without an accepted theory, the graph stops and reports that no cause was chosen. It does not guess.

### 4.6 Fix

**Role:** write a small patch, only when the change is certain.

Patches are built from the AST, not from text search. The fix agent handles eight patterns:

| Finding | Patch |
|---|---|
| Token expiry in the wrong unit | Remove the `* 1000` on the clock |
| Loop ignores a batch method | One call to the batch method with a list comprehension |
| Single `await` in a loop | `await asyncio.gather(...)` |
| HTTP call with no timeout | Add `timeout=10` |
| `time.sleep` in async code | `asyncio.sleep`, and add `import asyncio` if needed |
| `Depends(get_db())` | `Depends(get_db)` |
| Bare `except:` | `except Exception:` |
| JWT verification disabled | Turn verification back on |

Any other finding is reported with its file and line, and left for the developer. If the pattern does not match exactly, the fix agent returns nothing rather than a guessed patch.

### 4.7 Proof

**Role:** turn a patch into evidence.

1. **Select tests.** Starting from the finding’s folder, walk up to the nearest `tests/` directory. Prefer test functions that mention the finding’s function name, such as `tests/test_tokens.py::test_fresh_token_is_active`. Otherwise fall back to test files that mention the module.
2. **Find the project root.** Walk up to the nearest `pytest.ini` or `pyproject.toml`, so a nested project keeps its own imports.
3. **Two temporary copies.** Copy the repository twice. Leave one unchanged. Apply the patch to the other.
4. **Run pytest in both,** with a 40-second limit.
5. **Verdict.** **PROVEN** only when the original fails and the patched copy passes. Otherwise the case stays **OBSERVED**.
6. **Clean up.** Both copies are deleted. The developer’s files are never touched during proof.

---

## 5. How it was built

RepoMind was built in stages. Each stage was tested and pushed before the next one started.

1. **Scope.** The goal was a Python and LangGraph agent project that stands apart from generic chatbots, runs without paid keys, and is independent of any employer’s code.
2. **Demo first.** Paystream was written with two real bugs and failing tests, so the investigation could be proven end to end.
3. **Workflow.** The LangGraph graph was built with parallel specialists, a critic loop, and a proof step. Its first job was to solve Paystream correctly, including rejecting the latency trap.
4. **CLI and packaging.** A Typer CLI, a Rich report, a `pyproject.toml`, and a bundled fixture made it installable with `pip`.
5. **Windows testing.** Running on Windows found a missing `pytest` dependency. The failed proof was diagnosed and the dependency was moved into the main install.
6. **Any Python folder.** Question-based retrieval, a numbered findings table, and new Ruff rules made `scan` and `explain` work outside the demo.
7. **Focused backend scope.** Security, async, FastAPI, and reliability checks were added, plus five new safe patches, each with a proof test.
8. **False-positive fixes.** Scanning RepoMind itself exposed three bugs: string `.find()` treated as a query, the wrong tests chosen for the demo bug, and an unrelated `except Exception` accepted as the cause of a login failure. Each fix added a regression test.
9. **Release.** CI on GitHub Actions, the static site on GitHub Pages, and version 0.3.2 on PyPI.

---

## 6. Current scope and limits

Be precise about these when presenting the project.

- **Python only.** It does not analyze other languages.
- **Focused checks.** It covers the security, async, FastAPI, and reliability patterns listed above. It is not a general bug finder.
- **Patches for eight patterns.** Other findings are reported, not rewritten.
- **Proof needs a test.** Without a related test, a patch stays unproven.
- **The model does not decide.** Recon, Security, Performance, Hypothesis, Critic, Fix, and Proof use AST analysis, Ruff, and explicit rules. If Qwen2.5-Coder 1.5B (or 7B) is downloaded locally, it rewrites the case note **after** the critic accepts a cause. It cannot change the finding, the patch, or the proven verdict. Without the model, the factual summary is used.
- **Proof runs the project’s tests locally.** Only run it on code you trust. The temporary copies are not a security sandbox.

---

## 7. Why it stands out on a resume

Most portfolio AI projects look like this:

> Built a chatbot with LangChain and OpenAI.

That mainly shows API integration. RepoMind shows engineering judgment:

| Signal | What RepoMind demonstrates |
|---|---|
| Real agent orchestration | A LangGraph graph with parallel nodes, shared state, and a conditional retry loop, not a single prompt |
| Self-correction | A critic that rejects plausible but wrong causes, shown in the demo |
| Verification | A fix counts only when a failing test passes after it |
| Code analysis | AST parsing, structural patches, and exact line numbers |
| Privacy by design | Runs locally, uploads nothing, and needs no paid API |
| Shipping | Published on PyPI, with CI, a live site, and a Windows-tested install |
| Honesty | It says “no cause chosen” instead of guessing |

It also fits a coherent profile: **Python backend engineering, agentic workflows, and verified results**.

### Resume entry

**RepoMind — Local Python Code Investigation Agent** | *Python, LangGraph, AST, pytest, Typer, Next.js*
[PyPI](https://pypi.org/project/repomind-local/) · [GitHub](https://github.com/Mdazar123/repomind) · [Live case](https://mdazar123.github.io/repomind/)

- Built and published a pip-installable CLI (`repomind-local`) that investigates Python repositories locally, with no source upload and no paid API.
- Designed a seven-agent LangGraph workflow with parallel security and performance specialists, a hypothesis agent, and a critic that rejects causes that do not match the reported symptom.
- Implemented AST-based detection for security, async, FastAPI, and reliability issues, plus structural patches for eight patterns, including timeouts, `asyncio.sleep`, `Depends`, and JWT verification.
- Marked a fix proven only when the related pytest test failed on the original code and passed on a patched temporary copy.
- Shipped with GitHub Actions CI, a static Next.js case site on GitHub Pages, and a PyPI release.

Use real numbers only. The current verifiable ones are seven agents, eight patch patterns, 12 automated tests, and version 0.3.2.

### A 30-second explanation

> RepoMind is a local Python debugging agent. You give it a repository and a symptom, like “fresh tokens are rejected.” Specialist agents file problems with exact lines. A hypothesis agent picks a cause, and a critic rejects it if it doesn’t explain the symptom. In the demo, it rejects a slow-loop theory because a slow loop can’t cause a 401. Then a fix agent writes a small patch, and the proof agent runs the related test before and after in temporary copies. It only says “proven” when the test goes from red to green. It runs on your machine and is published on PyPI.

### Likely interview questions

**Why LangGraph instead of one prompt?**
The investigation has real control flow: two agents run in parallel, their results merge, and the critic can send work back. A graph makes that explicit, testable, and bounded to two retries.

**How do you avoid hallucinated findings?**
A finding must cite a line that exists on disk. The critic re-reads that line and checks that it matches the question. Patches are built from the AST, and a fix is proven by a test, not by the tool’s own claim.

**What happens when it doesn’t know?**
It says so. If no finding matches the question, the report says no cause was chosen. If no test covers a patch, the patch stays unproven.

**Where does an LLM fit?**
The workflow is designed so an LLM can become one node, for example a local Qwen model that proposes theories. That model would still have to pass the critic and the proof. That is the planned next step. Today the decisions are deterministic.

**What was the hardest bug?**
Scanning RepoMind itself. It chose its own tests to prove the demo bug, so the result was “passed before, failed after.” The fix was to select tests from the finding’s nearest `tests/` folder and run pytest from that project’s root.

---

## 8. Next steps

In order of value:

1. **Test on real projects.** Run on several open-source FastAPI repositories and record precision: real findings versus noise.
2. **Local LLM node.** Use Qwen2.5-Coder through `llama.cpp` to propose theories and explain findings, still gated by the critic and the proof.
3. **Isolated proof.** Run tests in a container with no network, so proof is safe on untrusted code.
4. **More patches.** Move from reporting to fixing for resource leaks and SQL parameterization.
5. **CI integration.** A GitHub Action that runs `repomind scan` on pull requests and comments with the findings.
