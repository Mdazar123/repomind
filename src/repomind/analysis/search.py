"""Find the functions a question is actually about."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from repomind.analysis.index import iter_files

_STOP = {
    "the",
    "and",
    "why",
    "how",
    "what",
    "when",
    "with",
    "this",
    "that",
    "from",
    "your",
    "have",
    "does",
    "for",
    "are",
    "was",
    "can",
    "not",
    "into",
    "about",
    "fail",
    "fails",
    "failed",
    "failure",
    "error",
    "errors",
    "bug",
    "bugs",
    "broken",
    "issue",
    "issues",
    "work",
    "working",
}


def question_terms(question: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", question.lower())
        if word not in _STOP
    ]


def retrieve(repo: Path, question: str, limit: int = 5) -> list[dict]:
    words = question_terms(question)
    if not words:
        return []
    scored: list[tuple[int, dict]] = []
    for path in iter_files(repo):
        if path.suffix != ".py" or "tests" in path.parts:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            segment = ast.get_source_segment(source, node) or ""
            name = node.name.lower()
            score = 0
            for word in words:
                pattern = rf"\b{re.escape(word)}\b"
                if re.search(pattern, name):
                    score += 5
                elif re.search(pattern, segment.lower()):
                    score += 1
            if score < 5:
                continue
            start = max(1, node.lineno)
            end = min(len(lines), (node.end_lineno or node.lineno))
            preview = "\n".join(lines[start - 1 : min(end, start + 12)])
            scored.append(
                (
                    score,
                    {
                        "file": path.relative_to(repo).as_posix(),
                        "line": node.lineno,
                        "name": node.name,
                        "snippet": preview,
                    },
                )
            )
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in scored[:limit]]
