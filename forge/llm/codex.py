"""CodexProvider — shell out to an OpenAI codex-style CLI.

Stub: wire your actual `codex` invocation in `_invoke_codex` when ready.
The shape (subprocess + stdin prompt + stdout JSON response) is in place
so the agent / tracer / budget plumbing already works the moment you fill
the gap.

CodexProvider flattens the message list into a single text prompt before
shelling out, because the codex CLI's non-interactive entry point takes
a single prompt. A future SDK-based provider (Anthropic, OpenAI Responses
API) should pass the full message array through so multi-turn tool-use
survives.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from forge.llm.provider import CompletionResponse, Message


@dataclass
class CodexConfig:
    binary: str = "codex"
    model: str = "gpt-5-codex"
    extra_args: tuple[str, ...] = ()
    timeout_seconds: int = 120


class CodexProvider:
    def __init__(self, config: CodexConfig | None = None):
        self.config = config or CodexConfig()
        self.model = self.config.model

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> CompletionResponse:
        prompt = _flatten(messages)
        raw = self._invoke_codex(prompt)
        try:
            parsed = json.loads(raw)
            text = parsed.get("output_text") or parsed.get("text") or raw
            tokens_in = int(parsed.get("usage", {}).get("input_tokens", len(prompt) // 4))
            tokens_out = int(parsed.get("usage", {}).get("output_tokens", len(text) // 4))
            cost_usd = float(parsed.get("usage", {}).get("cost_usd", 0.0))
        except (json.JSONDecodeError, AttributeError, TypeError):
            text = raw
            tokens_in = len(prompt) // 4
            tokens_out = len(text) // 4
            cost_usd = 0.0

        return CompletionResponse(
            text=text,
            model=self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
        )

    def _invoke_codex(self, prompt: str) -> str:
        """Actually run the codex CLI. Replace with your verified invocation.

        Raises NotImplementedError until you wire it. The shape below is
        a reasonable starting point — confirm against your codex version
        before relying on it.
        """
        raise NotImplementedError(
            "CodexProvider is a stub. Implement _invoke_codex with your "
            "verified codex CLI invocation, then remove this raise."
        )
        # Reference shape (uncomment + verify against your installed codex):
        # cmd = [
        #     self.config.binary,
        #     "exec",
        #     "--output-format=json",
        #     "--model", self.config.model,
        #     *self.config.extra_args,
        # ]
        # result = subprocess.run(
        #     cmd,
        #     input=prompt,
        #     capture_output=True,
        #     text=True,
        #     timeout=self.config.timeout_seconds,
        # )
        # if result.returncode != 0:
        #     raise RuntimeError(f"codex failed: {result.stderr.strip()}")
        # return result.stdout


def _flatten(messages: list[Message]) -> str:
    return "\n\n".join(f"[{m.role}]\n{m.content}" for m in messages)
