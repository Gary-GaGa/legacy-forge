"""CLI tests via Click's CliRunner.

Verify that the public CLI surface composes — refactors of cli.py
shouldn't silently break user-facing commands. These do NOT exercise
real git or real LLM providers.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from forge.cli import _budget_for, _repo_root, main

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_cli_version():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "forge" in result.output.lower()


def test_cli_phases_lists_pipeline_with_wired_column():
    result = CliRunner().invoke(main, ["phases"])
    assert result.exit_code == 0
    assert "p0_inventory" in result.output
    assert "p6_verify" in result.output
    # `wired` column header should be present.
    assert "wired" in result.output


def test_cli_trace_ls_handles_empty_db(tmp_path: Path, monkeypatch):
    # Run from a scratch dir; trace DB will be created on demand but be empty.
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["trace", "ls"])
    assert result.exit_code == 0
    # Title row from the rich table should appear.
    assert "recent runs" in result.output


def test_cli_eval_ls_known_agent(monkeypatch):
    # Need cwd inside the repo so `evals/cases/` is discovered.
    monkeypatch.chdir(_REPO_ROOT)
    result = CliRunner().invoke(main, ["eval", "ls", "java-lang-migrator"])
    assert result.exit_code == 0
    assert "java-lang-migrator" in result.output


def test_cli_eval_ls_no_cases(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["eval", "ls", "java-lang-migrator"])
    assert result.exit_code == 0
    assert "no cases" in result.output.lower()


def test_cli_eval_run_echo_emits_wiring_warning(monkeypatch):
    monkeypatch.chdir(_REPO_ROOT)
    result = CliRunner().invoke(
        main, ["eval", "run", "java-lang-migrator", "--provider", "echo"]
    )
    # Result may pass or fail; the warning must be present either way.
    assert "wiring" in result.output.lower()
    assert "echo" in result.output.lower()


# ---- _repo_root walks up to the project root ------------------------------


def test_repo_root_walks_up_to_pyproject(monkeypatch):
    deep = _REPO_ROOT / "forge" / "llm"
    monkeypatch.chdir(deep)
    assert _repo_root() == _REPO_ROOT


def test_repo_root_falls_back_to_cwd(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    # tmp_path has neither .git nor pyproject — must fall back to cwd.
    assert _repo_root() == tmp_path.resolve()


# ---- Per-agent budget caps wire through the CLI ---------------------------


def test_budget_for_picks_up_agent_caps():
    budget = _budget_for("java-lang-migrator", _REPO_ROOT / "prompts")
    # The shipped v1.meta.yaml sets max_iterations: 5 — must override default 30.
    assert budget.max_iterations == 5


def test_budget_for_unknown_agent_returns_defaults():
    budget = _budget_for("does-not-exist", _REPO_ROOT / "prompts")
    assert budget.max_iterations == 30   # Budget() default
