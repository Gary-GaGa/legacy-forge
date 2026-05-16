"""Phase DAG + agent dispatch.

Pillar 6 (Orchestration). Phases run as a DAG: an Agent only fires when its
dependencies are satisfied. Within a phase, tasks fan out across worktrees.

This is a skeleton. The first concrete wiring lives in
`forge.orchestrator.phases.default_pipeline()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable


@dataclass(frozen=True)
class Phase:
    name: str
    description: str
    depends_on: tuple[str, ...] = ()
    run: Callable[["PhaseContext"], "PhaseResult"] | None = None


@dataclass
class PhaseContext:
    run_id: str
    repo_root: str
    artifacts: dict[str, object] = field(default_factory=dict)


@dataclass
class PhaseResult:
    phase: str
    status: str   # ok | error | skipped
    artifacts: dict[str, object] = field(default_factory=dict)
    error: str | None = None


class CycleError(RuntimeError):
    pass


def toposort(phases: Iterable[Phase]) -> list[Phase]:
    by_name = {p.name: p for p in phases}
    visited: dict[str, int] = {}   # 0 = visiting, 1 = done
    order: list[Phase] = []

    def visit(p: Phase) -> None:
        state = visited.get(p.name)
        if state == 1:
            return
        if state == 0:
            raise CycleError(f"cycle through phase '{p.name}'")
        visited[p.name] = 0
        for dep in p.depends_on:
            if dep not in by_name:
                raise KeyError(f"phase '{p.name}' depends on unknown phase '{dep}'")
            visit(by_name[dep])
        visited[p.name] = 1
        order.append(p)

    for p in by_name.values():
        visit(p)
    return order


class Orchestrator:
    def __init__(self, phases: list[Phase]):
        self.phases = toposort(phases)

    def run(self, ctx: PhaseContext) -> list[PhaseResult]:
        results: list[PhaseResult] = []
        failed_deps: set[str] = set()

        for phase in self.phases:
            if any(d in failed_deps for d in phase.depends_on):
                results.append(PhaseResult(phase.name, status="skipped"))
                failed_deps.add(phase.name)
                continue

            if phase.run is None:
                results.append(PhaseResult(phase.name, status="skipped"))
                continue

            try:
                result = phase.run(ctx)
                results.append(result)
                if result.status != "ok":
                    failed_deps.add(phase.name)
                else:
                    ctx.artifacts.update(result.artifacts)
            except Exception as e:
                results.append(
                    PhaseResult(phase.name, status="error", error=f"{type(e).__name__}: {e}")
                )
                failed_deps.add(phase.name)

        return results


def default_pipeline() -> list[Phase]:
    """The legacy-forge canonical 7-phase pipeline.

    All `run` callables are None for now — wire concrete agents as they land.
    """
    return [
        Phase("p0_inventory",         "Scan legacy repo: modules, deps, entry points, DB use"),
        Phase("p1_characterize",      "Generate behavior-preserving tests",
              depends_on=("p0_inventory",)),
        Phase("p2_compile_upgrade",   "Java 7 -> 11 -> 17 -> 21 compile-only upgrade",
              depends_on=("p1_characterize",)),
        Phase("p3_framework_upgrade", "javax -> jakarta, old Spring -> Boot 3, Ant -> Gradle",
              depends_on=("p2_compile_upgrade",)),
        Phase("p4_api_extract",       "Extract business logic from controllers; OpenAPI spec",
              depends_on=("p3_framework_upgrade",)),
        Phase("p5_angular_scaffold",  "Generate Angular scaffolding from OpenAPI + JSP map",
              depends_on=("p4_api_extract",)),
        Phase("p6_verify",            "Strangler-fig dual-run; diff-based equivalence verification",
              depends_on=("p5_angular_scaffold",)),
    ]
