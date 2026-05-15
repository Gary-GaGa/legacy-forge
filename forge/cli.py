"""`forge` CLI entry point.

Minimal commands to verify the skeleton works end-to-end:

    forge trace ls
    forge worktree create <name>
    forge worktree ls
    forge worktree release <name>
    forge eval run <agent>
    forge phases
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from forge import __version__
from forge.evals.runner import discover_cases
from forge.orchestrator import default_pipeline
from forge.tracer import Tracer
from forge.worktree import WorktreeManager

console = Console()


def _repo_root() -> Path:
    return Path.cwd()


def _trace_db() -> Path:
    return _repo_root() / ".forge" / "trace.sqlite"


@click.group()
@click.version_option(__version__, prog_name="forge")
def main() -> None:
    """legacy-forge: AI-agent Harness for legacy refactoring."""


# ---- trace ----------------------------------------------------------------

@main.group()
def trace() -> None:
    """Inspect run traces."""


@trace.command("ls")
@click.option("--limit", default=20, show_default=True)
def trace_ls(limit: int) -> None:
    t = Tracer(_trace_db())
    runs = t.list_runs(limit=limit)
    table = Table(title="recent runs")
    for col in ("run_id", "started_at", "ended_at", "span_count", "cost_usd", "errors"):
        table.add_column(col)
    for r in runs:
        table.add_row(*(str(r.get(c, "")) for c in (
            "run_id", "started_at", "ended_at", "span_count", "cost_usd", "errors"
        )))
    console.print(table)


# ---- worktree -------------------------------------------------------------

@main.group()
def worktree() -> None:
    """Manage isolated worktrees for agent tasks."""


@worktree.command("create")
@click.argument("name")
@click.option("--base", default="HEAD", show_default=True)
def worktree_create(name: str, base: str) -> None:
    wm = WorktreeManager(_repo_root())
    lease = wm.create(name, base_ref=base)
    console.print(f"[green]created[/] {lease.path}  branch={lease.branch}")


@worktree.command("ls")
def worktree_ls() -> None:
    wm = WorktreeManager(_repo_root())
    table = Table(title="worktree leases")
    for col in ("name", "branch", "owner_id", "expires_at"):
        table.add_column(col)
    for l in wm.list():
        table.add_row(l.name, l.branch, l.owner_id, str(l.expires_at))
    console.print(table)


@worktree.command("release")
@click.argument("name")
def worktree_release(name: str) -> None:
    wm = WorktreeManager(_repo_root())
    wm.release(name)
    console.print(f"[yellow]released[/] {name}")


@worktree.command("gc")
def worktree_gc() -> None:
    wm = WorktreeManager(_repo_root())
    reclaimed = wm.gc()
    console.print(f"reclaimed: {reclaimed!r}")


# ---- eval -----------------------------------------------------------------

@main.group()
def eval() -> None:
    """Run eval suites for agents."""


@eval.command("ls")
@click.argument("agent", required=False)
def eval_ls(agent: str | None) -> None:
    cases_dir = _repo_root() / "evals" / "cases"
    cases = discover_cases(cases_dir, agent)
    if not cases:
        console.print("[yellow]no cases found[/]")
        return
    table = Table(title=f"eval cases ({agent or 'all'})")
    for col in ("id", "agent", "fixture"):
        table.add_column(col)
    for c in cases:
        table.add_row(c.id, c.agent, c.fixture)
    console.print(table)


@eval.command("run")
@click.argument("agent")
def eval_run(agent: str) -> None:
    cases_dir = _repo_root() / "evals" / "cases"
    cases = discover_cases(cases_dir, agent)
    if not cases:
        console.print(f"[yellow]no cases for agent '{agent}'[/]")
        raise SystemExit(1)
    console.print(
        f"[dim]found {len(cases)} case(s) — wiring an actual runner is the next step[/]"
    )


# ---- phases ---------------------------------------------------------------

@main.command()
def phases() -> None:
    """Show the canonical refactor phase DAG."""
    table = Table(title="default pipeline")
    for col in ("phase", "depends_on", "description"):
        table.add_column(col)
    for p in default_pipeline():
        table.add_row(p.name, ", ".join(p.depends_on) or "-", p.description)
    console.print(table)


if __name__ == "__main__":
    main()
