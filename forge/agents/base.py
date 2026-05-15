"""Agent base class.

Each role-specific agent (Java Lang Migrator, API Extractor, …) subclasses
Agent and implements `run`. The Harness gives them:
- a Tracer span (Pillar 4)
- a Budget (Pillar 6 loop control)
- a Worktree lease (Pillar 5)
- a typed Input/Output schema (Pillar 2 tool ergonomics)

This file does NOT call any LLM. The actual call lives in subclasses that
plug in a provider adapter — we want one place to swap providers (Claude,
codex, local model) without touching agent logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel

from forge.budget import Budget
from forge.tracer import Tracer

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


@dataclass
class AgentContext:
    run_id: str
    tracer: Tracer
    budget: Budget
    worktree_path: str | None = None
    attrs: dict[str, str] = field(default_factory=dict)


class Agent(ABC, Generic[In, Out]):
    """Subclass and set Input / Output to your pydantic schemas."""

    name: str = "unnamed-agent"
    Input: type[BaseModel]
    Output: type[BaseModel]

    @abstractmethod
    def run(self, ctx: AgentContext, inp: In) -> Out:
        """Do the work. Subclasses should:

        1. Open a tracer span (`ctx.tracer.span("agent", self.name, run_id=ctx.run_id)`)
        2. Inside the span, perform LLM/tool calls — each in its own child span
        3. After every LLM round-trip, call `ctx.budget.tick(...)` and
           `ctx.budget.bail_if_exhausted()`
        4. Return a validated `Output` instance
        """
