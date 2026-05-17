"""Smoke tests for the Harness skeleton.

These verify the scaffolding holds together — they do NOT call any LLM.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.agents.base import AgentContext, AgentOutputError
from forge.agents.java_lang_migrator import (
    JavaLangMigrator,
    JavaLangMigratorInput,
    extract_java_block,
    extract_review_notes,
)
from forge.budget import Budget, BudgetExhausted
from forge.evals.case import EvalCase, Expectation
from forge.evals.runner import score
from forge.llm.echo import MARKER, EchoProvider
from forge.llm.provider import CompletionResponse, Message
from forge.memory.store import PhaseMemory
from forge.orchestrator import (
    CycleError,
    Orchestrator,
    Phase,
    PhaseContext,
    PhaseResult,
    default_pipeline,
    toposort,
)
from forge.prompt import BudgetCaps, Prompt, PromptMeta, load_prompt, render
from forge.provenance import Trail, read_trail, write_trail
from forge.tracer import Tracer, new_run_id

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROMPTS_DIR = _REPO_ROOT / "prompts"
_FIXTURES_DIR = _REPO_ROOT / "evals" / "fixtures"


def test_default_pipeline_is_dag():
    phases = default_pipeline()
    ordered = toposort(phases)
    seen: set[str] = set()
    for p in ordered:
        for dep in p.depends_on:
            assert dep in seen, f"{p.name} runs before its dep {dep}"
        seen.add(p.name)


def test_orchestrator_detects_cycle():
    phases = [
        Phase("a", "", depends_on=("b",)),
        Phase("b", "", depends_on=("a",)),
    ]
    with pytest.raises(CycleError):
        toposort(phases)


def test_tracer_records_span(tmp_path: Path):
    t = Tracer(tmp_path / "trace.sqlite")
    run_id = new_run_id()
    with t.span("agent", "test-agent", run_id=run_id) as s:
        s.model = "claude-test"
        s.tokens_in = 100
        s.tokens_out = 50
        s.cost_usd = 0.001
    runs = t.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == run_id
    spans = t.query_run(run_id)
    assert len(spans) == 1
    assert spans[0]["status"] == "ok"
    assert spans[0]["tokens_in"] == 100


def test_tracer_records_error(tmp_path: Path):
    t = Tracer(tmp_path / "trace.sqlite")
    run_id = new_run_id()
    with pytest.raises(ValueError):
        with t.span("agent", "bad", run_id=run_id):
            raise ValueError("nope")
    spans = t.query_run(run_id)
    assert spans[0]["status"] == "error"
    assert "nope" in spans[0]["error_message"]


def test_budget_trips():
    b = Budget(max_iterations=2)
    b.tick()
    b.bail_if_exhausted()
    b.tick()
    b.bail_if_exhausted()
    b.tick()
    with pytest.raises(BudgetExhausted) as ei:
        b.bail_if_exhausted()
    assert ei.value.dimension == "iterations"


def test_eval_score_pass_and_fail():
    case = EvalCase(
        id="t1",
        agent="x",
        fixture="x.java",
        expect=Expectation(contains=["jakarta"], not_contains=["javax"]),
    )
    assert score("import jakarta.x;", case).passed
    bad = score("import javax.x; import jakarta.x;", case)
    assert not bad.passed
    assert any("javax" in f for f in bad.failures)


def test_phase_memory_roundtrip(tmp_path: Path):
    m = PhaseMemory(tmp_path / "mem.sqlite")
    m.put("p2", "skipped_files", ["Foo.java", "Bar.java"])
    assert m.get("p2", "skipped_files") == ["Foo.java", "Bar.java"]
    assert m.list_keys("p2") == ["skipped_files"]
    m.delete("p2", "skipped_files")
    assert m.get("p2", "skipped_files") is None


# ---- Java Lang Migrator ----------------------------------------------------


def test_prompt_loads_and_renders():
    prompt = load_prompt("java-lang-migrator", "v1", prompts_dir=_PROMPTS_DIR)
    rendered = render(
        prompt,
        target_java=21,
        source_path="Foo.java",
        source_code="class Foo {}",
    )
    assert "Target Java: 21" in rendered
    assert "class Foo {}" in rendered
    assert "{{" not in rendered  # all placeholders filled


def test_prompt_unfilled_placeholder_raises():
    p = Prompt(agent="x", version="v1", body="hello {{name}}", meta=PromptMeta())
    with pytest.raises(ValueError, match="unfilled placeholders"):
        render(p)  # name not supplied


def test_echo_provider_wraps_in_marker():
    provider = EchoProvider()
    src = "class Demo { void f() {} }"
    fake_prompt = f"some preamble\n\n```java\n{src}\n```\n"
    resp = provider.complete([Message(role="user", content=fake_prompt)])
    assert MARKER in resp.text
    assert src in resp.text
    assert resp.model == "echo-noop-v0"
    assert resp.tokens_in > 0


def test_extract_java_block_picks_last_fenced_block():
    text = "noise\n```java\nA\n```\nmore\n```java\nFINAL\n```\n"
    assert extract_java_block(text) == "FINAL"


def test_extract_review_notes_finds_forge_review_markers():
    code = "class X {}\n// FORGE-REVIEW: timezone semantics uncertain\n"
    assert extract_review_notes(code) == ["timezone semantics uncertain"]


def test_java_lang_migrator_end_to_end(tmp_path: Path):
    tracer = Tracer(tmp_path / "trace.sqlite")
    budget = Budget()
    run_id = new_run_id()
    ctx = AgentContext(run_id=run_id, tracer=tracer, budget=budget)

    agent = JavaLangMigrator(EchoProvider(), prompts_dir=_PROMPTS_DIR)
    src = (_FIXTURES_DIR / "anonymous_runnable.java").read_text(encoding="utf-8")
    out = agent.run(
        ctx,
        JavaLangMigratorInput(
            source_path="anonymous_runnable.java", source_code=src, target_java=21
        ),
    )

    assert MARKER in out.migrated_code
    assert "class TaskRunner" in out.migrated_code
    assert out.model == "echo-noop-v0"
    assert out.prompt_version == "v1"

    spans = tracer.query_run(run_id)
    kinds = {s["kind"] for s in spans}
    assert {"agent", "llm"} <= kinds
    assert budget.iterations == 1
    assert budget.tokens_used > 0


def test_provenance_roundtrip(tmp_path: Path):
    target = tmp_path / "Foo.java"
    target.write_text("class Foo {}", encoding="utf-8")
    trail = Trail(
        target_path=str(target),
        agent="java-lang-migrator",
        prompt_version="v1",
        model="claude-test",
        run_id="r1",
        source_refs=["legacy@deadbeef:src/old/Foo.java"],
        verifiers_passed=["compile"],
    )
    sidecar = write_trail(trail)
    loaded = read_trail(sidecar)
    assert loaded.agent == "java-lang-migrator"
    assert loaded.source_refs == ["legacy@deadbeef:src/old/Foo.java"]


# ---- Output validation / repair loop --------------------------------------


class _BrokenProvider:
    """Always returns prose with no fenced java block."""

    model = "broken-mock-v0"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages, *, max_tokens=4096, tools=None):
        self.calls += 1
        return CompletionResponse(
            text="I cannot do that. Here is some prose instead.",
            model=self.model,
            tokens_in=10,
            tokens_out=10,
            cost_usd=0.0,
        )


class _EventuallyOKProvider:
    """Returns prose on the first call, a valid fenced block on the second."""

    model = "flaky-mock-v0"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages, *, max_tokens=4096, tools=None):
        self.calls += 1
        text = (
            "no code block here, sorry"
            if self.calls == 1
            else "```java\nclass Fixed {}\n```"
        )
        return CompletionResponse(
            text=text, model=self.model, tokens_in=10, tokens_out=10, cost_usd=0.0
        )


def test_agent_raises_after_repair_attempts_exhausted(tmp_path: Path):
    tracer = Tracer(tmp_path / "trace.sqlite")
    budget = Budget()
    run_id = new_run_id()
    ctx = AgentContext(run_id=run_id, tracer=tracer, budget=budget)

    provider = _BrokenProvider()
    agent = JavaLangMigrator(provider, prompts_dir=_PROMPTS_DIR)
    with pytest.raises(AgentOutputError):
        agent.run(
            ctx,
            JavaLangMigratorInput(
                source_path="x.java", source_code="class X {}", target_java=21
            ),
        )
    # Initial attempt + max_repair_attempts retries.
    assert provider.calls == JavaLangMigrator.max_repair_attempts + 1


def test_agent_recovers_via_repair_attempt(tmp_path: Path):
    tracer = Tracer(tmp_path / "trace.sqlite")
    budget = Budget()
    run_id = new_run_id()
    ctx = AgentContext(run_id=run_id, tracer=tracer, budget=budget)

    provider = _EventuallyOKProvider()
    agent = JavaLangMigrator(provider, prompts_dir=_PROMPTS_DIR)
    out = agent.run(
        ctx,
        JavaLangMigratorInput(
            source_path="x.java", source_code="class X {}", target_java=21
        ),
    )
    assert "class Fixed" in out.migrated_code
    assert provider.calls == 2
    # Two LLM round-trips => two budget ticks.
    assert budget.iterations == 2


# ---- Orchestrator end-to-end ----------------------------------------------


def test_orchestrator_runs_wired_phase_and_propagates_artifacts():
    seen: list[str] = []

    def run_a(ctx: PhaseContext) -> PhaseResult:
        seen.append(ctx.run_id)
        return PhaseResult("a", status="ok", artifacts={"k": "v"})

    def run_b(ctx: PhaseContext) -> PhaseResult:
        # Artifact from `a` should be visible to `b`.
        assert ctx.artifacts.get("k") == "v"
        return PhaseResult("b", status="ok")

    orch = Orchestrator([
        Phase("a", "", run=run_a),
        Phase("b", "", run=run_b, depends_on=("a",)),
    ])
    results = orch.run(PhaseContext(run_id="r1", repo_root="."))
    assert seen == ["r1"]
    assert [r.status for r in results] == ["ok", "ok"]


def test_orchestrator_skips_after_failed_dep():
    def run_fail(ctx: PhaseContext) -> PhaseResult:
        return PhaseResult("a", status="error", error="boom")

    def run_b(ctx: PhaseContext) -> PhaseResult:   # pragma: no cover - must not run
        raise AssertionError("b ran despite a failing")

    orch = Orchestrator([
        Phase("a", "", run=run_fail),
        Phase("b", "", run=run_b, depends_on=("a",)),
    ])
    results = {r.phase: r.status for r in orch.run(PhaseContext(run_id="r1", repo_root="."))}
    assert results == {"a": "error", "b": "skipped"}


def test_orchestrator_skips_unwired_phases():
    """Default pipeline has all phases with run=None — must finish, all skipped."""
    orch = Orchestrator(default_pipeline())
    results = orch.run(PhaseContext(run_id="r1", repo_root="."))
    assert all(r.status == "skipped" for r in results)


# ---- Per-agent budget caps -------------------------------------------------


def test_prompt_meta_loads_budget_caps():
    prompt = load_prompt("java-lang-migrator", "v1", prompts_dir=_PROMPTS_DIR)
    assert isinstance(prompt.meta.budget, BudgetCaps)
    # Each cap should be present in the meta file we ship.
    assert prompt.meta.budget.max_iterations is not None
    assert prompt.meta.budget.max_iterations <= 30   # tighter than the global default


def test_budget_caps_defaults_when_missing():
    meta = PromptMeta()
    assert meta.budget.max_tokens is None
    assert meta.budget.max_iterations is None
