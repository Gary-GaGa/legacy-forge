"""Eval case schema.

A case lives in evals/cases/<agent>/<id>.yaml and looks like:

    id: javax-import-rewrite-001
    agent: java-lang-migrator
    fixture: fixtures/struts_action_simple.java
    input:
        target_java: 21
    expect:
        # all assertions in `expect` must hold for the case to pass
        contains: ["jakarta.servlet"]
        not_contains: ["javax.servlet"]
        compiles: true
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Expectation(BaseModel):
    contains: list[str] = Field(default_factory=list)
    not_contains: list[str] = Field(default_factory=list)
    compiles: bool | None = None
    custom_checks: list[str] = Field(default_factory=list)   # names resolved by the runner


class EvalCase(BaseModel):
    id: str
    agent: str
    fixture: str
    input: dict = Field(default_factory=dict)
    expect: Expectation = Field(default_factory=Expectation)
    description: str | None = None

    @classmethod
    def load(cls, path: Path) -> "EvalCase":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)
