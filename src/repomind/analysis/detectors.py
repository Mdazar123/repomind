"""Detectors the specialist agents are allowed to file.

Each one points at a line. A hypothesis without a line is not a finding.
"""

from __future__ import annotations

import ast
from pathlib import Path

from repomind.analysis.index import iter_files


def _finding(
    detector: str,
    category: str,
    confidence: float,
    file: str,
    line: int,
    title: str,
    detail: str,
    evidence: str,
    function: str | None,
    extra: dict | None = None,
) -> dict:
    return {
        "id": f"{detector}:{file}:{line}",
        "detector": detector,
        "category": category,
        "confidence": confidence,
        "severity": "high" if confidence >= 0.8 else "medium",
        "file": file,
        "line": line,
        "title": title,
        "detail": detail,
        "evidence": evidence.strip(),
        "function": function,
        "extra": extra or {},
    }


def _line(source: str, lineno: int) -> str:
    rows = source.splitlines()
    if lineno < 1 or lineno > len(rows):
        return ""
    return rows[lineno - 1]


def _batch_name(method: str, names: set[str]) -> str | None:
    candidates = [
        f"{method}_accounts",
        f"{method}_many",
        f"{method}_batch",
        f"{method}_all",
    ]
    for candidate in candidates:
        if candidate in names and candidate != method:
            return candidate
    return None


def _enclosing_function(tree: ast.AST, target: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target:
                    return node.name
    return None


def _collect_names(repo: Path) -> set[str]:
    names: set[str] = set()
    for path in iter_files(repo):
        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
    return names


def _is_times_thousand(node: ast.AST) -> ast.AST | None:
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult):
        return None
    for side in (node.left, node.right):
        other = node.right if side is node.left else node.left
        if isinstance(side, ast.Constant) and side.value in (1000, 1000.0):
            return other
    return None


def detect(repo: Path) -> list[dict]:
    from repomind.analysis.checks import extra_checks

    names = _collect_names(repo)
    findings: list[dict] = []
    for path in iter_files(repo):
        if path.suffix != ".py":
            continue
        rel = path.relative_to(repo).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        findings.extend(_expiry_findings(tree, source, rel))
        findings.extend(_loop_findings(tree, source, rel, names))
        findings.extend(extra_checks(tree, source, rel))
    return findings


def _expiry_findings(tree: ast.AST, source: str, rel: str) -> list[dict]:
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for comparator in node.comparators:
            other = _is_times_thousand(comparator)
            if other is None:
                continue
            left = ast.get_source_segment(source, node.left) or ""
            right = ast.get_source_segment(source, comparator) or ""
            blob = f"{left} {right}".lower()
            if "exp" not in blob and "token" not in blob:
                continue
            function = _enclosing_function(tree, node)
            evidence = _line(source, node.lineno)
            other_src = ast.get_source_segment(source, other) or "the clock"
            found.append(
                _finding(
                    detector="expiry_unit_mismatch",
                    category="auth",
                    confidence=0.9,
                    file=rel,
                    line=node.lineno,
                    title="Token expiry is compared in the wrong unit",
                    detail=(
                        f"`{function or 'this check'}` compares `{left.strip()}` with "
                        f"`{right.strip()}`. The clock is scaled by 1000, so a unix-second "
                        f"`exp` is always behind `{other_src} * 1000`."
                    ),
                    evidence=evidence,
                    function=function,
                    extra={"scaled": right.strip()},
                )
            )
    return found


def _awaited_call(node: ast.AST) -> ast.Call | None:
    if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
        return node.value
    return None


def _loop_findings(tree: ast.AST, source: str, rel: str, names: set[str]) -> list[dict]:
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        if len(node.body) != 1:
            continue
        statement = node.body[0]
        call = _batchable_extend(statement)
        bare = _bare_await(statement)
        inner = call or bare
        if inner is None or not isinstance(inner.func, ast.Attribute):
            continue
        method = inner.func.attr
        batch = _batch_name(method, names)
        function = _enclosing_function(tree, node)
        evidence = _line(source, node.lineno)
        if batch and call is not None:
            obj = ast.get_source_segment(source, inner.func.value) or "the client"
            found.append(
                _finding(
                    detector="unused_batch_call",
                    category="latency",
                    confidence=0.88,
                    file=rel,
                    line=node.lineno,
                    title=f"Loop calls `{method}` even though `{batch}` exists",
                    detail=(
                        f"`{function or 'this function'}` awaits `{obj}.{method}` once per "
                        f"item. `{batch}` is already defined and performs the same read in "
                        f"one call."
                    ),
                    evidence=evidence,
                    function=function,
                    extra={"method": method, "batch": batch},
                )
            )
            continue
        if bare is not None:
            obj = ast.get_source_segment(source, inner.func.value) or "the client"
            found.append(
                _finding(
                    detector="await_in_loop",
                    category="latency",
                    confidence=0.7,
                    file=rel,
                    line=node.lineno,
                    title=f"`{method}` is awaited once per item",
                    detail=(
                        f"`{function or 'this function'}` awaits `{obj}.{method}` inside a "
                        f"loop, so the calls run one after another."
                    ),
                    evidence=evidence,
                    function=function,
                    extra={"method": method},
                )
            )
    return found


def _batchable_extend(statement: ast.stmt) -> ast.Call | None:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return None
    call = statement.value
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "extend":
        return None
    if len(call.args) != 1:
        return None
    return _awaited_call(call.args[0])


def _bare_await(statement: ast.stmt) -> ast.Call | None:
    if isinstance(statement, ast.Expr):
        return _awaited_call(statement.value)
    return None
