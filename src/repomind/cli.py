"""RepoMind command line."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from repomind import __version__
from repomind.analysis.fixes import propose_edit
from repomind.analysis.proof import run_pytest, select_tests
from repomind.cases import TOKEN_CASE
from repomind.model import cache_dir, download, llama_available, model_path
from repomind.render import render_report
from repomind.workflow import bundled_paystream, investigate

app = typer.Typer(add_completion=False, help="Investigate a repository locally, then prove the patch.")
console = Console()
model_app = typer.Typer(help="Download an optional local coding model.")
app.add_typer(model_app, name="model")


def _store(repo: Path, report: dict) -> Path:
    folder = repo / ".repomind"
    folder.mkdir(exist_ok=True)
    path = folder / "latest.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


@app.callback()
def main_callback() -> None:
    """RepoMind keeps the repository on this machine."""


@app.command()
def doctor() -> None:
    """Check the local tools this CLI can use."""
    import shutil

    rows = [
        ("Python", True, "investigation runtime"),
        ("Git", shutil.which("git") is not None, "optional, for your own repo"),
        ("Ruff", True, "installed with RepoMind"),
        ("Local model runtime", llama_available(), "optional, pip install \"repomind-local[model]\""),
        ("Qwen 1.5B weights", model_path("1.5b") is not None, str(cache_dir())),
        ("Qwen 7B weights", model_path("7b") is not None, "optional larger model"),
    ]
    table = Table(title=f"RepoMind {__version__}")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for name, ok, detail in rows:
        table.add_row(name, "ready" if ok else "missing", detail)
    console.print(table)
    console.print("Scans do not need a model. A local model only rewrites the case note.")


@app.command()
def scan(
    path: Path = typer.Argument(Path("."), exists=True, file_okay=False, resolve_path=True),
) -> None:
    """Index a repository and file every defect the specialists can prove from the code."""
    report = investigate(path, problem="", use_notes=False)
    saved = _store(path, report)
    render_report(report)
    console.print(f"Saved {saved}")


@app.command()
def explain(
    question: str = typer.Argument(...),
    path: Path = typer.Argument(Path("."), exists=True, file_okay=False, resolve_path=True),
) -> None:
    """Investigate one symptom. The critic rejects theories that do not explain it."""
    report = investigate(path, problem=question, use_notes=True)
    saved = _store(path, report)
    render_report(report)
    console.print(f"Saved {saved}")


@app.command()
def demo(
    json_out: Path | None = typer.Option(None, "--json-out", help="Write the case report as JSON."),
) -> None:
    """Run the bundled Paystream token case. Nothing is uploaded."""
    report = investigate(bundled_paystream(), problem=TOKEN_CASE, use_notes=True)
    render_report(report)
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        console.print(f"Wrote {json_out}")


@app.command()
def fix(
    number: int = typer.Argument(1, min=1),
    path: Path = typer.Argument(Path("."), exists=True, file_okay=False, resolve_path=True),
    yes: bool = typer.Option(False, "--yes", help="Apply the edit without asking."),
) -> None:
    """Show a prepared edit and apply it only after confirmation."""
    report_path = path / ".repomind" / "latest.json"
    if not report_path.exists():
        raise typer.BadParameter("Run repomind scan or repomind explain in this repository first.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    candidates = list(report.get("findings") or [])
    if not candidates and report.get("root_cause"):
        candidates.append(report["root_cause"])
        candidates.extend(report.get("also_found") or [])
    if number > len(candidates):
        raise typer.BadParameter(f"This case has {len(candidates)} findings.")
    finding = candidates[number - 1]
    edit = propose_edit(path, finding)
    if not edit:
        console.print("RepoMind cannot safely rewrite this finding automatically.")
        raise typer.Exit(code=1)
    console.print(edit["diff"])
    console.print(edit["explanation"])
    target = path / edit["path"]
    current = target.read_text(encoding="utf-8")
    if current != edit["before"]:
        console.print("The file changed after the investigation. Run the scan again.")
        raise typer.Exit(code=1)
    if not yes and not typer.confirm("Apply this patch?", default=False):
        console.print("Left the file unchanged.")
        raise typer.Exit()
    target.write_text(edit["after"], encoding="utf-8")
    tests = select_tests(path, finding["category"], finding["file"], finding.get("function"))
    if tests:
        result = run_pytest(path, tests)
        status = "passed" if result["passed"] else "failed"
        console.print(f"Applied {edit['path']}. Targeted tests {status}.")
        console.print(result.get("output", ""))
    else:
        console.print(f"Applied {edit['path']}. No targeted test was found.")


@model_app.command("download")
def model_download(
    size: str = typer.Option("1.5b", "--size", help="1.5b or 7b"),
) -> None:
    """Download Qwen2.5-Coder GGUF weights into the local cache."""
    path = download(size)
    console.print(f"Model ready at {path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
