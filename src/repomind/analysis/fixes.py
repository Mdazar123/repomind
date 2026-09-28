"""Turn a filed finding into a minimal source edit.

Edits are structural. If the shape is not one the fixer understands, it
returns nothing rather than guessing a patch.
"""

from __future__ import annotations

import ast
import difflib
from pathlib import Path

from repomind.analysis.detectors import _batch_name, _is_times_thousand
from repomind.analysis.index import iter_files


def _offset(source: str, lineno: int, col: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(lines[index]) for index in range(lineno - 1)) + col


def _replace(source: str, node: ast.AST, text: str) -> str:
    start = _offset(source, node.lineno, node.col_offset)
    end = _offset(source, node.end_lineno or node.lineno, node.end_col_offset or 0)
    return source[:start] + text + source[end:]


def _function_names(repo: Path) -> set[str]:
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


def _unified(path: str, before: str, after: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)


def propose_edit(repo: Path, finding: dict) -> dict | None:
    path = repo / finding["file"]
    if not path.exists():
        return None
    before = path.read_text(encoding="utf-8", errors="replace")
    if finding["detector"] == "expiry_unit_mismatch":
        after = _fix_expiry(before)
        explanation = (
            "Compare the expiry in the same unit the token was issued in. "
            "Remove the ×1000 on the clock."
        )
    elif finding["detector"] == "unused_batch_call":
        after = _fix_batch(before, _function_names(repo))
        batch = finding.get("extra", {}).get("batch", "the batch method")
        explanation = f"Replace the per-item read with one call to `{batch}`."
    elif finding["detector"] == "await_in_loop":
        after = _fix_gather(before)
        explanation = "Run the awaited calls concurrently with asyncio.gather."
    else:
        return None
    if not after or after == before:
        return None
    return {
        "path": finding["file"],
        "before": before,
        "after": after,
        "diff": _unified(finding["file"], before, after),
        "explanation": explanation,
    }


def _fix_expiry(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for comparator in node.comparators:
            other = _is_times_thousand(comparator)
            if other is None:
                continue
            left = ast.get_source_segment(source, node.left) or ""
            if "exp" not in left.lower() and "token" not in left.lower():
                segment = ast.get_source_segment(source, comparator) or ""
                if "exp" not in segment.lower():
                    continue
            other_src = ast.get_source_segment(source, other)
            if not other_src:
                continue
            return _replace(source, comparator, other_src)
    return None


def _fix_batch(source: str, names: set[str]) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)) or len(node.body) != 1:
            continue
        statement = node.body[0]
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            continue
        extend = statement.value
        if not isinstance(extend.func, ast.Attribute) or extend.func.attr != "extend":
            continue
        if len(extend.args) != 1 or not isinstance(extend.args[0], ast.Await):
            continue
        inner = extend.args[0].value
        if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Attribute):
            continue
        if len(inner.args) != 1:
            continue
        batch = _batch_name(inner.func.attr, names)
        if not batch:
            continue
        rows = ast.get_source_segment(source, extend.func.value)
        obj = ast.get_source_segment(source, inner.func.value)
        arg = ast.get_source_segment(source, inner.args[0])
        target = ast.get_source_segment(source, node.target)
        iterable = ast.get_source_segment(source, node.iter)
        if not all([rows, obj, arg, target, iterable]):
            continue
        replacement = (
            f"{rows}.extend(await {obj}.{batch}([{arg} for {target} in {iterable}]))"
        )
        return _replace(source, node, replacement)
    return None


def _fix_gather(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)) or len(node.body) != 1:
            continue
        statement = node.body[0]
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Await):
            continue
        inner = statement.value.value
        if not isinstance(inner, ast.Call):
            continue
        call_src = ast.get_source_segment(source, inner)
        target = ast.get_source_segment(source, node.target)
        iterable = ast.get_source_segment(source, node.iter)
        if not all([call_src, target, iterable]):
            continue
        replacement = f"await asyncio.gather(*({call_src} for {target} in {iterable}))"
        updated = _replace(source, node, replacement)
        return _ensure_asyncio(updated)
    return None


def _ensure_asyncio(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    for node in tree.body:
        if isinstance(node, ast.Import):
            if any(alias.name == "asyncio" for alias in node.names):
                return source
        if isinstance(node, ast.ImportFrom) and node.module == "asyncio":
            return source
    lines = source.splitlines(keepends=True)
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    if insert_at < len(lines) and "coding" in lines[insert_at]:
        insert_at += 1
    # Keep a module docstring and future imports above the new import.
    index = insert_at
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("from __future__") or stripped.startswith(('"""', "'''")):
            if stripped.startswith(('"""', "'''")) and stripped.count(stripped[:3]) < 2:
                index += 1
                while index < len(lines) and '"""' not in lines[index] and "'''" not in lines[index]:
                    index += 1
                index += 1
                continue
            index += 1
            continue
        if stripped == "":
            index += 1
            continue
        break
    lines.insert(index, "import asyncio\n")
    return "".join(lines)
