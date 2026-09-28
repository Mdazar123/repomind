"""Run a targeted pytest file in a throwaway copy of the workspace."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def select_tests(repo: Path, category: str, finding_file: str, function: str | None = None) -> list[str]:
    del category
    stem = Path(finding_file).stem
    tests_dir = repo / "tests"
    if not tests_dir.exists():
        return []
    named: list[str] = []
    files: list[str] = []
    for path in sorted(tests_dir.glob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(repo).as_posix()
        if function and function in text:
            named.extend(_tests_mentioning(text, relative, function))
        if stem and stem in text:
            files.append(relative)
    if named:
        return named[:4]
    return files[:2]


def _tests_mentioning(text: str, relative: str, function: str) -> list[str]:
    import ast

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    matches: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            segment = ast.get_source_segment(text, node) or ""
            if function in segment:
                matches.append(f"{relative}::{node.name}")
    return matches


def _copy(repo: Path) -> Path:
    destination = Path(tempfile.mkdtemp(prefix="repomind-proof-"))
    shutil.copytree(
        repo,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".pytest_cache"),
    )
    return destination


def run_pytest(repo: Path, tests: list[str], timeout: int = 40) -> dict:
    if not tests:
        return {
            "passed": False,
            "returncode": 1,
            "output": "No test file matched this finding.",
            "tests": [],
        }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short", *tests],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        return {
            "passed": completed.returncode == 0,
            "returncode": completed.returncode,
            "output": output[-4000:],
            "tests": tests,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "returncode": 124,
            "output": f"pytest timed out after {timeout}s.",
            "tests": tests,
        }


def prove(repo: Path, edit: dict, tests: list[str]) -> dict:
    baseline_dir = _copy(repo)
    patched_dir = _copy(repo)
    try:
        baseline = run_pytest(baseline_dir, tests)
        target = patched_dir / edit["path"]
        target.write_text(edit["after"], encoding="utf-8")
        patched = run_pytest(patched_dir, tests)
    finally:
        shutil.rmtree(baseline_dir, ignore_errors=True)
        shutil.rmtree(patched_dir, ignore_errors=True)
    proven = (not baseline["passed"]) and patched["passed"]
    return {
        "tests": tests,
        "baseline": baseline,
        "patched": patched,
        "proven": proven,
    }
