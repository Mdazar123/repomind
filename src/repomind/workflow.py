"""LangGraph investigation. Specialists file evidence. The critic can send it back."""

from __future__ import annotations

import hashlib
import operator
import subprocess
import sys
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from repomind.analysis.detectors import detect
from repomind.analysis.fixes import propose_edit
from repomind.analysis.index import index_repo
from repomind.analysis.proof import prove, select_tests
from repomind.analysis.search import retrieve
from repomind.analysis.symptoms import (
    choose_hypothesis,
    finding_misses_question,
    primary_symptom,
    symptom_conflict,
)


class InvestigationState(TypedDict):
    repo: str
    problem: str
    use_notes: bool
    index: dict
    catalog: list
    findings: Annotated[list, operator.add]
    dismissed: Annotated[list, operator.add]
    round: int
    hypothesis: dict | None
    critiques: Annotated[list, operator.add]
    edit: dict | None
    proof: dict | None
    report: dict | None
    log: Annotated[list, operator.add]


def bundled_paystream() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "paystream"


def _snippet(repo: Path, file: str, line: int, radius: int = 2) -> str:
    path = repo / file
    if not path.exists():
        return ""
    rows = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, line - radius)
    end = min(len(rows), line + radius)
    chunk = []
    for number in range(start, end + 1):
        marker = ">" if number == line else " "
        chunk.append(f"{marker} {number:4}  {rows[number - 1]}")
    return "\n".join(chunk)


def _line_text(repo: Path, file: str, line: int) -> str:
    path = repo / file
    if not path.exists():
        return ""
    rows = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line < 1 or line > len(rows):
        return ""
    return rows[line - 1].strip()


def _ruff_findings(repo: Path) -> list[dict]:
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                str(repo),
                "--select",
                "F821,F822,F823,E722,B006,B007,S102,S106,S107,S110,S112,S602,S608,ASYNC",
                "--exclude",
                "tests",
                "--output-format",
                "json",
                "--exit-zero",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    import json

    try:
        payload = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return []
    findings = []
    for item in payload:
        code = item.get("code") or ""
        if code.startswith("ASYNC"):
            category = "latency"
        elif code in {"F821", "F822", "F823", "E722"} or code.startswith("BLE"):
            category = "defect"
        else:
            category = "security"
        file = Path(item["filename"])
        try:
            rel = file.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = file.as_posix()
        line = int(item["location"]["row"])
        findings.append(
            {
                "id": f"ruff:{code}:{rel}:{line}",
                "detector": "ruff",
                "category": category,
                "confidence": _ruff_confidence(code),
                "severity": "medium",
                "file": rel,
                "line": line,
                "title": f"{code}: {item.get('message', 'Ruff finding')}",
                "detail": item.get("message", ""),
                "evidence": _line_text(repo, rel, line),
                "function": None,
                "extra": {"code": code, "url": item.get("url")},
            }
        )
    return findings


def _ruff_confidence(code: str) -> float:
    if code in {"F821", "F822", "F823"}:
        return 0.78
    if code in {"E722", "S602", "S608"} or code.startswith("BLE"):
        return 0.7
    if code.startswith("ASYNC"):
        return 0.66
    return 0.55


def _dedupe(findings: list[dict]) -> list[dict]:
    best: dict[tuple[str, int], dict] = {}
    for finding in findings:
        key = (finding["file"], int(finding["line"]))
        current = best.get(key)
        if current is None or finding["confidence"] > current["confidence"]:
            best[key] = finding
    return list(best.values())


def _memo(agent: str, title: str, body: str, tone: str = "info") -> dict:
    return {"agent": agent, "title": title, "body": body, "tone": tone}


def recon(state: InvestigationState) -> dict:
    repo = Path(state["repo"])
    index = index_repo(repo)
    catalog = _dedupe(detect(repo) + _ruff_findings(repo))
    catalog.sort(key=lambda item: item["confidence"], reverse=True)
    catalog = catalog[:30]
    routes = index.get("routes") or []
    route_text = ", ".join(f"{item['verb']} {item['path']}" for item in routes[:6]) or "none marked"
    body = (
        f"Indexed {len(index.get('files') or [])} files, "
        f"{len(index.get('functions') or [])} functions, "
        f"{len(index.get('tests') or [])} tests. Routes: {route_text}."
    )
    if index.get("notes"):
        body += " On-call notes are in the workspace and will be treated as a lead, not as proof."
    memos = [_memo("recon", "Repository indexed", body, "evidence")]
    hits = retrieve(repo, state.get("problem") or "")
    if hits:
        index["hits"] = hits
        listed = "\n".join(f"{item['file']}:{item['line']} {item['name']}" for item in hits)
        memos.append(_memo("recon", "Read the functions that match the question", listed, "evidence"))
    return {
        "index": index,
        "catalog": catalog,
        "log": memos,
    }


def security_agent(state: InvestigationState) -> dict:
    mine = [item for item in state["catalog"] if item["category"] != "latency"]
    if not mine:
        body = "No authentication or secret-handling defect was filed from the files I read."
    else:
        lines = [f"{item['file']}:{item['line']} — {item['title']}" for item in mine[:8]]
        extra = f"\n+ {len(mine) - 8} more" if len(mine) > 8 else ""
        body = "Filed from the code:\n" + "\n".join(lines) + extra
    return {"findings": mine, "log": [_memo("security", "Security pass", body, "evidence")]}


def performance_agent(state: InvestigationState) -> dict:
    mine = [item for item in state["catalog"] if item["category"] == "latency"]
    if not mine:
        body = "No per-item I/O loop or unused batch API was filed."
    else:
        lines = [f"{item['file']}:{item['line']} — {item['title']}" for item in mine]
        body = "Filed from the data path:\n" + "\n".join(lines)
    return {"findings": mine, "log": [_memo("performance", "Performance pass", body, "evidence")]}


def hypothesize(state: InvestigationState) -> dict:
    dismissed = set(state.get("dismissed") or [])
    notes = ""
    index = state.get("index") or {}
    if state.get("use_notes"):
        notes = index.get("notes") or ""
    choice = choose_hypothesis(
        state.get("findings") or [],
        state.get("problem") or "",
        notes,
        int(state.get("round") or 0),
        dismissed,
    )
    if choice is None:
        return {
            "hypothesis": None,
            "log": [_memo("hypothesis", "No theory left", "Nothing with a file and a line survived.", "info")],
        }
    if int(state.get("round") or 0) == 0 and notes:
        title = "Leading with the on-call note"
        body = (
            "The notes mention a latency lead before the 401s, so this pass starts there. "
            f"{choice['title']} ({choice['file']}:{choice['line']})."
        )
    else:
        title = "Theory selected from the case statement"
        body = f"{choice['title']} ({choice['file']}:{choice['line']}). {choice['detail']}"
    return {"hypothesis": choice, "log": [_memo("hypothesis", title, body, "info")]}


def critic(state: InvestigationState) -> dict:
    repo = Path(state["repo"])
    hypothesis = state.get("hypothesis")
    if not hypothesis:
        critique = {
            "accepted": False,
            "title": "Nothing to challenge",
            "body": "No theory was filed, so there is nothing to accept.",
            "finding_id": None,
        }
        return {
            "critiques": [critique],
            "log": [_memo("critic", critique["title"], critique["body"], "challenge")],
        }
    actual = _line_text(repo, hypothesis["file"], int(hypothesis["line"]))
    evidence = (hypothesis.get("evidence") or "").strip()
    if not actual or (evidence and evidence not in actual and actual not in evidence):
        critique = {
            "accepted": False,
            "title": "Evidence does not match the file",
            "body": f"The cited line in {hypothesis['file']} is not the line the theory describes.",
            "finding_id": hypothesis["id"],
        }
    else:
        conflict = None
        if state.get("problem"):
            conflict = finding_misses_question(state["problem"], hypothesis) or symptom_conflict(
                state["problem"], hypothesis["category"]
            )
        if conflict:
            critique = {
                "accepted": False,
                "title": "Theory rejected",
                "body": conflict,
                "finding_id": hypothesis["id"],
            }
        else:
            others = [
                item["title"]
                for item in state.get("findings") or []
                if item["id"] != hypothesis["id"]
            ]
            extra = ""
            if others:
                extra = f" I am not using “{others[0]}” as the cause."
            symptom = primary_symptom(state.get("problem") or "")
            critique = {
                "accepted": True,
                "title": "Theory stands",
                "body": (
                    f"Re-read {hypothesis['file']}:{hypothesis['line']}. "
                    f"The line is `{actual}`. "
                    f"It matches the reported {symptom} symptom.{extra}"
                ),
                "finding_id": hypothesis["id"],
            }
    update: dict = {
        "critiques": [critique],
        "log": [
            _memo(
                "critic",
                critique["title"],
                critique["body"],
                "proven" if critique["accepted"] else "challenge",
            )
        ],
    }
    if not critique["accepted"] and hypothesis:
        update["dismissed"] = [hypothesis["id"]]
        update["round"] = int(state.get("round") or 0) + 1
    return update


def route_critic(state: InvestigationState) -> str:
    if not state.get("hypothesis"):
        return "publish"
    latest = state["critiques"][-1]
    if latest["accepted"]:
        return "fix"
    if int(state.get("round") or 0) >= 2:
        return "publish"
    return "hypothesize"


def fix(state: InvestigationState) -> dict:
    hypothesis = state.get("hypothesis")
    if not hypothesis:
        return {"edit": None}
    edit = propose_edit(Path(state["repo"]), hypothesis)
    if not edit:
        return {
            "edit": None,
            "log": [
                _memo(
                    "fix",
                    "No automatic edit",
                    "The finding is real. RepoMind only rewrites patterns it can change without guessing: clock units, batch calls, async gathers, timeouts, time.sleep, Depends(), bare except, and disabled JWT checks.",
                    "info",
                )
            ],
        }
    return {
        "edit": edit,
        "log": [_memo("fix", f"Edit prepared for {edit['path']}", edit["explanation"], "evidence")],
    }


def route_fix(state: InvestigationState) -> str:
    if state.get("edit"):
        return "prove"
    return "publish"


def prove_node(state: InvestigationState) -> dict:
    repo = Path(state["repo"])
    hypothesis = state["hypothesis"]
    tests = select_tests(
        repo,
        hypothesis["category"],
        hypothesis["file"],
        hypothesis.get("function"),
    )
    if not tests:
        return {
            "proof": {
                "tests": [],
                "proven": False,
                "baseline": {"passed": False, "output": "No targeted test file was found.", "tests": []},
                "patched": {"passed": False, "output": "Proof was not run.", "tests": []},
            },
            "log": [_memo("proof", "No targeted test", "The edit was not executed because no test file matched it.", "info")],
        }
    result = prove(repo, state["edit"], tests)
    if result["proven"]:
        title = "Tests flipped from failing to passing"
        tone = "proven"
        body = (
            f"{', '.join(tests)} failed before the edit and passed after it. "
            "The workspace itself was not modified."
        )
    else:
        title = "Tests did not prove the edit"
        tone = "challenge"
        before = "passed" if result["baseline"]["passed"] else "failed"
        after = "passed" if result["patched"]["passed"] else "failed"
        body = f"Targeted tests {before} before the edit and {after} after it."
    return {"proof": result, "log": [_memo("proof", title, body, tone)]}


def route_proof(state: InvestigationState) -> str:
    proof = state.get("proof") or {}
    if proof.get("proven"):
        return "publish"
    if int(state.get("round") or 0) >= 2:
        return "publish"
    return "publish"


def _case_id(repo_name: str, problem: str) -> str:
    digest = hashlib.sha256(f"{repo_name}:{problem}".encode()).hexdigest()[:4].upper()
    return f"RM-{digest}"


def publish(state: InvestigationState) -> dict:
    repo = Path(state["repo"])
    hypothesis = state.get("hypothesis")
    proof = state.get("proof")
    edit = state.get("edit")
    critiques = state.get("critiques") or []
    accepted = bool(critiques and critiques[-1]["accepted"] and hypothesis)
    proven = bool(proof and proof.get("proven"))
    if proven:
        status = "proven"
    elif hypothesis and accepted:
        status = "observed"
    elif state.get("findings"):
        status = "observed"
    else:
        status = "unresolved"
    root = None
    if hypothesis and (not critiques or critiques[-1]["accepted"] or not state.get("problem")):
        root = {
            **hypothesis,
            "snippet": _snippet(repo, hypothesis["file"], int(hypothesis["line"])),
        }
    others = []
    root_id = root["id"] if root else None
    for finding in state.get("findings") or []:
        if finding["id"] == root_id:
            continue
        others.append({**finding, "snippet": _snippet(repo, finding["file"], int(finding["line"]))})
    index = state.get("index") or {}
    summary = _summary(state, status, root)
    report = {
        "id": _case_id(repo.name, state.get("problem") or ""),
        "product": "RepoMind",
        "repo_name": repo.name,
        "problem": state.get("problem") or "",
        "status": status,
        "summary": summary,
        "index": {
            "file_count": len(index.get("files") or []),
            "python_files": len(index.get("python_files") or []),
            "lines": index.get("lines") or 0,
            "routes": index.get("routes") or [],
            "tests": [
                {"name": item["name"], "file": item["file"]} for item in (index.get("tests") or [])
            ],
            "hits": index.get("hits") or [],
        },
        "log": state.get("log") or [],
        "critiques": critiques,
        "root_cause": root,
        "also_found": others,
        "findings": _numbered(root, others),
        "patch": None
        if not edit
        else {
            "path": edit["path"],
            "diff": edit["diff"],
            "explanation": edit["explanation"],
        },
        "proof": proof,
    }
    return {
        "report": report,
        "log": [_memo("publish", "Case filed", summary, "proven" if proven else "info")],
    }


def _numbered(root: dict | None, others: list[dict]) -> list[dict]:
    ordered = []
    if root:
        ordered.append(root)
    ordered.extend(others)
    for number, finding in enumerate(ordered, start=1):
        finding["number"] = number
    return ordered


def _summary(state: InvestigationState, status: str, root: dict | None) -> str:
    if status == "proven" and root and state.get("proof"):
        tests = ", ".join(state["proof"].get("tests") or [])
        rejected = [item for item in state.get("critiques") or [] if not item["accepted"]]
        challenge = ""
        if rejected:
            challenge = "The critic rejected an earlier theory that did not explain the symptom. "
        return (
            f"{challenge}{root['title']} in {root['file']}:{root['line']}. "
            f"{tests} failed before the edit and passed after it."
        )
    if state.get("problem") and not (state.get("critiques") and state["critiques"][-1]["accepted"]):
        return (
            "No filed line mentions the subject of the question. "
            "RepoMind did not choose a cause."
        )
    if root:
        return f"{root['title']} in {root['file']}:{root['line']}. {root['detail']}"
    if state.get("findings"):
        return "Findings were filed, and none of them was promoted to a proven patch."
    return "The specialists did not file a defect with a supporting line."


def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("recon", recon)
    graph.add_node("security", security_agent)
    graph.add_node("performance", performance_agent)
    graph.add_node("hypothesize", hypothesize)
    graph.add_node("critic", critic)
    graph.add_node("fix", fix)
    graph.add_node("prove", prove_node)
    graph.add_node("publish", publish)
    graph.add_edge(START, "recon")
    graph.add_edge("recon", "security")
    graph.add_edge("recon", "performance")
    graph.add_edge("security", "hypothesize")
    graph.add_edge("performance", "hypothesize")
    graph.add_edge("hypothesize", "critic")
    graph.add_conditional_edges(
        "critic",
        route_critic,
        {"fix": "fix", "hypothesize": "hypothesize", "publish": "publish"},
    )
    graph.add_conditional_edges("fix", route_fix, {"prove": "prove", "publish": "publish"})
    graph.add_conditional_edges("prove", route_proof, {"publish": "publish"})
    graph.add_edge("publish", END)
    return graph.compile()


_GRAPH = None


def investigate(repo: Path, problem: str = "", use_notes: bool = False) -> dict:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    state = {
        "repo": str(repo.resolve()),
        "problem": problem,
        "use_notes": use_notes,
        "index": {},
        "catalog": [],
        "findings": [],
        "dismissed": [],
        "round": 0,
        "hypothesis": None,
        "critiques": [],
        "edit": None,
        "proof": None,
        "report": None,
        "log": [],
    }
    result = _GRAPH.invoke(state)
    report = result["report"]
    report["log"] = result.get("log") or report.get("log") or []
    return report
