"""Terminal case file."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()


def render_report(report: dict) -> None:
    status = report.get("status", "unresolved").upper()
    header = Text()
    header.append("RepoMind", style="bold")
    header.append("  local investigation\n", style="dim")
    header.append(report.get("id", ""), style="bold")
    header.append(f"   {report.get('repo_name', '')}   {status}")
    console.print(Panel(header, border_style="white"))
    if report.get("problem"):
        console.print(Panel(report["problem"], title="Case", border_style="yellow"))
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Agent", style="bold", width=14)
    table.add_column("Note")
    for memo in report.get("log") or []:
        if memo.get("agent") == "publish":
            continue
        table.add_row(memo.get("agent", ""), f"{memo.get('title', '')}\n{memo.get('body', '')}")
    console.print(table)
    findings = report.get("findings") or []
    if findings:
        found = Table(title="Findings", expand=True)
        found.add_column("#", width=4)
        found.add_column("Where")
        found.add_column("What")
        for finding in findings:
            found.add_row(
                str(finding.get("number", "")),
                f"{finding['file']}:{finding['line']}",
                finding["title"],
            )
        console.print(found)
        console.print("Next: repomind fix 1    shows the first patch and asks before writing.")
    root = report.get("root_cause")
    if root:
        console.print(
            Panel(
                f"{root['title']}\n{root['file']}:{root['line']}\n\n{root.get('snippet') or root.get('evidence', '')}",
                title="Root cause",
                border_style="green" if report.get("status") == "proven" else "white",
            )
        )
    patch = report.get("patch")
    if patch and patch.get("diff"):
        console.print(Syntax(patch["diff"], "diff", theme="ansi_dark", word_wrap=True))
        console.print(patch.get("explanation", ""))
    proof = report.get("proof") or {}
    if proof:
        baseline = proof.get("baseline") or {}
        patched = proof.get("patched") or {}
        console.print(
            Panel(
                f"before: {'passed' if baseline.get('passed') else 'failed'}\n"
                f"after:  {'passed' if patched.get('passed') else 'failed'}\n\n"
                f"{(patched.get('output') or '')[-1200:]}",
                title="Sandbox proof",
                border_style="green" if proof.get("proven") else "red",
            )
        )
    console.print(report.get("summary", ""))
