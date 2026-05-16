"""Provider protocol + completion response shape.

Pillar 2 (Tool Ergonomics) — agents see ONE shape regardless of which
backend is wired in. Every provider returns the same dataclass so
tracer / budget / cost dashboards work uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CompletionResponse:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float = 0.0
    cache_read: int = 0
    cache_write: int = 0


class LLMProvider(Protocol):
    """Minimum contract every backend must satisfy."""

    model: str

    def complete(self, prompt: str, *, max_tokens: int = 4096) -> CompletionResponse:
        ...
