"""Provider protocol + message / completion shapes.

Pillar 2 (Tool Ergonomics). Providers see a list of messages and may emit
tool_calls. Agents see ONE shape regardless of which backend is wired in.

The Protocol is intentionally shaped for multi-turn tool-using agents from
day one: an LLM round-trip takes a `list[Message]` and may return
`tool_calls` for the agent to execute, then append `tool` messages on the
next call. Single-shot agents simply pass one user message and ignore
tool_calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class Message:
    role: Role
    content: str
    tool_call_id: str | None = None


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, object] = field(default_factory=dict)
    call_id: str = ""


@dataclass
class CompletionResponse:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float = 0.0
    cache_read: int = 0
    cache_write: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "stop"  # stop | tool_use | length | error


class LLMProvider(Protocol):
    """Minimum contract every backend must satisfy.

    One call = one round-trip. The agent owns the loop: if a response has
    `tool_calls`, the agent executes them, appends `tool` messages, and
    calls `complete` again. Providers do not own multi-turn state.
    """

    model: str

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> CompletionResponse:
        ...
