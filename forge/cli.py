"""`forge` CLI entry point.

    forge phases
    forge trace ls
    forge worktree create <name> | ls | release <name> | gc
    forge eval ls [agent]
    forge eval run <agent> [--provider echo|codex]
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from forge import __version__
from forge.agents import registry as agent_registry
from forge.agents.base import AgentContext
from forge.agents.java_lang_migrator import JavaLangMigratorInput
from forge.budget import Budget
from forge.evals.case import EvalCase
from forge.evals.runner import discover_cases, score
from forge.llm.codex import CodexProvider
from forge.llm.echo import EchoProvider
from forge.llm.provider import LLMProvider
from forge.orchestrator import default_pipeline
from forge.tracer import Tracer, new_run_id
from forge.worktree import WorktreeManager

console = Console()


def _repo_root() -> Path:
    return Path.cwd()


def _trace_db() -> Path:
    return _repo_root() / ".forge" / "trace.sqlite"


def _make_provider(name: str) -> LLMProvider:
    if name == "echo":
        return EchoProvider()
    if name == "codex":
        return CodexProvider()
    raise click.ClickException(f"unknown provider: {name}. Try 'echo' or 'codex'.")


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
@click.option(
    "--provider",
    type=click.Choice(["echo", "codex"]),
    default="echo",
    show_default=True,
    help="LLM provider to drive the agent.",
)
def eval_run(agent: str, provider: str) -> None:
    cases_dir = _repo_root() / "evals" / "cases"
    fixtures_dir = _repo_root() / "evals" / "fixtures"
    prompts_dir = _repo_root() / "prompts"

    cases = discover_cases(cases_dir, agent)
    if not cases:
        console.print(f"[yellow]no cases for agent '{agent}'[/]")
        raise SystemExit(1)

    try:
        factory = agent_registry.get(agent)
    except KeyError as e:
        raise click.ClickException(str(e))

    provider_obj = _make_provider(provider)
    agent_obj = factory(provider_obj, prompts_dir)

    tracer = Tracer(_trace_db())
    budget = Budget()
    run_id = new_run_id()

    table = Table(title=f"{agent} — eval results (provider={provider}, run={run_id[:8]})")
    table.add_column("case")
    table.add_column("result")
    table.add_column("notes")

    passed = 0
    with tracer.span("run", f"eval:{agent}", run_id=run_id) as run_span:
        for case in cases:
            ctx = AgentContext(
                run_id=run_id,
                tracer=tracer,
                budget=budget,
                attrs={"phase": "eval", "agent": agent},
            )
            output_text = _run_one(agent, case, fixtures_dir, agent_obj, ctx)
            result = score(output_text, case)
            if result.passed:
                passed += 1
                table.add_row(case.id, "[green]PASS[/]", "")
            else:
                table.add_row(case.id, "[red]FAIL[/]", "; ".join(result.failures))
        run_span.attrs = {"cases": str(len(cases)), "passed": str(passed)}

    console.print(table)
    console.print(
        f"pass rate: [bold]{passed}/{len(cases)}[/] "
        f"({passed/len(cases):.0%})  •  budget: {budget.snapshot()}"
    )
    if passed != len(cases):
        raise SystemExit(1)


def _run_one(
    agent: str,
    case: EvalCase,
    fixtures_dir: Path,
    agent_obj,
    ctx: AgentContext,
) -> str:
    fixture_path = fixtures_dir / case.fixture
    source = fixture_path.read_text(encoding="utf-8")

    if agent == "java-lang-migrator":
        inp = JavaLangMigratorInput(
            source_path=case.fixture,
            source_code=source,
            target_java=int(case.input.get("target_java", 21)),
        )
        out = agent_obj.run(ctx, inp)
        return out.migrated_code

    raise click.ClickException(f"no input adapter wired for agent '{agent}'")


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
