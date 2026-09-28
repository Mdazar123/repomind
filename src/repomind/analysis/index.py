"""Read a workspace into a small code index. Python only, on purpose."""

from __future__ import annotations

import ast
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}


def iter_files(repo: Path) -> list[Path]:
    found: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.stat().st_size > 200_000:
            continue
        found.append(path)
    return sorted(found)


def read_notes(repo: Path) -> str:
    path = repo / "ops" / "incident_notes.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def index_repo(repo: Path) -> dict:
    files = iter_files(repo)
    python_files: list[dict] = []
    functions: list[dict] = []
    routes: list[dict] = []
    calls: list[dict] = []
    tests: list[dict] = []
    function_names: set[str] = set()
    total_lines = 0

    for path in files:
        rel = _rel(repo, path)
        if path.suffix != ".py":
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        total_lines += source.count("\n") + 1
        try:
            tree = ast.parse(source)
        except SyntaxError:
            python_files.append({"path": rel, "lines": source.count("\n") + 1, "functions": []})
            continue
        file_functions: list[str] = []
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_names.add(node.name)
                file_functions.append(node.name)
                functions.append(
                    {
                        "name": node.name,
                        "file": rel,
                        "line": node.lineno,
                        "async": isinstance(node, ast.AsyncFunctionDef),
                    }
                )
                if node.lineno <= len(lines):
                    previous = lines[node.lineno - 2] if node.lineno >= 2 else ""
                    marker = previous.strip()
                    if marker.startswith("# route:"):
                        body = marker.split(":", 1)[1].strip()
                        verb, _, route = body.partition(" ")
                        routes.append(
                            {
                                "verb": verb,
                                "path": route,
                                "function": node.name,
                                "file": rel,
                                "line": node.lineno,
                            }
                        )
            if isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    name = node.func.id
                if name:
                    calls.append({"name": name, "file": rel, "line": node.lineno})
        if rel.startswith("tests/test_"):
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    asserts = [
                        item.lineno
                        for item in ast.walk(node)
                        if isinstance(item, ast.Assert)
                    ]
                    tests.append(
                        {
                            "name": node.name,
                            "file": rel,
                            "line": node.lineno,
                            "asserts": asserts,
                            "source": ast.get_source_segment(source, node) or "",
                        }
                    )
        python_files.append(
            {"path": rel, "lines": source.count("\n") + 1, "functions": file_functions}
        )

    return {
        "files": [_rel(repo, path) for path in files],
        "python_files": python_files,
        "lines": total_lines,
        "functions": functions,
        "function_names": sorted(function_names),
        "routes": routes,
        "calls": calls,
        "tests": tests,
        "notes": read_notes(repo),
    }
