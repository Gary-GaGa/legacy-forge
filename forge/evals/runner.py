"""Eval runner.

Pillar 3. Loads cases from evals/cases/<agent>/, runs the named agent against
each fixture, and scores the output against the case's expectations. Designed
to be called both locally (`forge eval run`) and from CI.

Scoring is intentionally simple at this stage — string contains / not_contains
plus a compile check hook. Add custom_checks (named callables in a registry)
as concrete agents land.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from forge.evals.case import EvalCase

CustomCheck = Callable[[str, EvalCase], tuple[bool, str]]
_CUSTOM_CHECKS: dict[str, CustomCheck] = {}


def register_check(name: str) -> Callable[[CustomCheck], CustomCheck]:
    def deco(fn: CustomCheck) -> CustomCheck:
        _CUSTOM_CHECKS[name] = fn
        return fn
    return deco


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    failures: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    agent: str
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if not self.cases:
            return 0.0
        return sum(1 for c in self.cases if c.passed) / len(self.cases)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.cases)


def discover_cases(cases_dir: Path, agent: str | None = None) -> list[EvalCase]:
    if not cases_dir.exists():
        return []
    cases: list[EvalCase] = []
    pattern = "**/*.yaml" if agent is None else f"{agent}/**/*.yaml"
    for path in cases_dir.glob(pattern):
        cases.append(EvalCase.load(path))
    if agent:
        cases = [c for c in cases if c.agent == agent]
    return cases


def score(output: str, case: EvalCase) -> CaseResult:
    failures: list[str] = []
    for needle in case.expect.contains:
        if needle not in output:
            failures.append(f"missing expected substring: {needle!r}")
    for needle in case.expect.not_contains:
        if needle in output:
            failures.append(f"unexpected substring present: {needle!r}")
    for check_name in case.expect.custom_checks:
        fn = _CUSTOM_CHECKS.get(check_name)
        if fn is None:
            failures.append(f"unknown custom_check: {check_name}")
            continue
        ok, msg = fn(output, case)
        if not ok:
            failures.append(f"custom_check {check_name}: {msg}")
    return CaseResult(case_id=case.id, passed=not failures, failures=failures)


def run(
    agent: str,
    *,
    runner: Callable[[EvalCase], str],
    cases_dir: Path,
) -> EvalReport:
    """Run all cases for `agent`.

    `runner` is a function that takes an EvalCase and produces the agent's
    output text. For the skeleton this is a stub; concrete agents will plug
    in their actual `run` method (wrapped so it returns a string).
    """
    report = EvalReport(agent=agent)
    for case in discover_cases(cases_dir, agent):
        output = runner(case)
        report.cases.append(score(output, case))
    return report
