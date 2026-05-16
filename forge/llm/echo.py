"""EchoProvider — offline wiring test provider.

It does not call any model. It extracts the last fenced code block from
the prompt (the source the agent wanted migrated), wraps it in a
passthrough marker, and returns it as a fresh fenced block.

This lets us:
- Run the full agent pipeline in CI without API keys
- Verify structural assertions (class preserved, no spurious drift)
- Measure trace / budget / provenance plumbing end-to-end

It is NOT a model. Real migration quality requires a real provider.
"""

from __future__ import annotations

import re

from forge.llm.provider import CompletionResponse

MARKER = "// FORGE: echo provider passthrough"


class EchoProvider:
    model = "echo-noop-v0"

    def complete(self, prompt: str, *, max_tokens: int = 4096) -> CompletionResponse:
        code = _last_fenced_block(prompt) or prompt
        text = f"```java\n{MARKER}\n{code}\n```"
        return CompletionResponse(
            text=text,
            model=self.model,
            tokens_in=max(1, len(prompt) // 4),
            tokens_out=max(1, len(text) // 4),
            cost_usd=0.0,
        )


def _last_fenced_block(text: str) -> str | None:
    matches = re.findall(r"```(?:\w+)?\n(.*?)\n```", text, flags=re.DOTALL)
    return matches[-1] if matches else None
