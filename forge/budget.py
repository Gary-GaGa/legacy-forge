"""Multi-dimensional budget tracker.

Pillar 6 (loop control). An agent stops when ANY of these caps trips:
- tokens (in + out, including cache reads)
- dollars (rolling cost)
- wallclock seconds
- iteration count (LLM round-trips)

Use as a context manager around an agent's main loop; call `tick()` after each
LLM call and `bail_if_exhausted()` before deciding to do another round.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


class BudgetExhausted(RuntimeError):
    def __init__(self, dimension: str, used: float, cap: float):
        super().__init__(f"budget '{dimension}' exhausted: used {used} > cap {cap}")
        self.dimension = dimension
        self.used = used
        self.cap = cap


@dataclass
class Budget:
    max_tokens: int = 1_000_000
    max_dollars: float = 5.0
    max_wallclock_s: float = 60 * 30
    max_iterations: int = 30

    tokens_used: int = 0
    dollars_used: float = 0.0
    iterations: int = 0
    started_at: float = field(default_factory=time.time)

    def tick(
        self,
        *,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cache_read: int = 0,
        dollars: float = 0.0,
    ) -> None:
        self.tokens_used += tokens_in + tokens_out + cache_read
        self.dollars_used += dollars
        self.iterations += 1

    @property
    def wallclock(self) -> float:
        return time.time() - self.started_at

    def bail_if_exhausted(self) -> None:
        if self.tokens_used > self.max_tokens:
            raise BudgetExhausted("tokens", self.tokens_used, self.max_tokens)
        if self.dollars_used > self.max_dollars:
            raise BudgetExhausted("dollars", self.dollars_used, self.max_dollars)
        if self.wallclock > self.max_wallclock_s:
            raise BudgetExhausted("wallclock", self.wallclock, self.max_wallclock_s)
        if self.iterations > self.max_iterations:
            raise BudgetExhausted("iterations", self.iterations, self.max_iterations)

    def snapshot(self) -> dict[str, float | int]:
        return {
            "tokens_used": self.tokens_used,
            "dollars_used": round(self.dollars_used, 4),
            "wallclock_s": round(self.wallclock, 2),
            "iterations": self.iterations,
        }
