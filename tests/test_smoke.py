"""Smoke tests for the Harness skeleton.

These verify the scaffolding holds together — they do NOT call any LLM.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.agents.base import AgentContext
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
from forge.memory.store import PhaseMemory
from forge.orchestrator import CycleError, Phase, default_pipeline, toposort
from forge.prompt import Prompt, PromptMeta, load_prompt, render
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
    resp = provider.complete(fake_prompt)
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
