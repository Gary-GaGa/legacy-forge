"""EchoProvider — wiring-test provider.

Does not call any model. Extracts the last fenced code block from the
latest user message, wraps it in a passthrough marker, and returns it
as a fresh fenced block.

EchoProvider exists for **wiring tests only**: it verifies that the
agent / tracer / budget / provenance plumbing composes. It is NOT a
model and produces NO real eval signal. `forge eval run --provider
echo` emits a warning to that effect.
"""

from __future__ import annotations

import re

from forge.llm.provider import CompletionResponse, Message

MARKER = "// FORGE: echo provider passthrough"


class EchoProvider:
    model = "echo-noop-v0"

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> CompletionResponse:
        last_user = _last_user_content(messages)
        code = _last_fenced_block(last_user) or last_user
        text = f"```java\n{MARKER}\n{code}\n```"
        prompt_size = sum(len(m.content) for m in messages)
        return CompletionResponse(
            text=text,
            model=self.model,
            tokens_in=max(1, prompt_size // 4),
            tokens_out=max(1, len(text) // 4),
            cost_usd=0.0,
        )


def _last_user_content(messages: list[Message]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


def _last_fenced_block(text: str) -> str | None:
    matches = re.findall(r"```(?:\w+)?\n(.*?)\n```", text, flags=re.DOTALL)
    return matches[-1] if matches else None
