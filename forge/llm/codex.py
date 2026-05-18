"""CodexProvider — shell out to the OpenAI codex CLI.

For Windows / corporate-intranet deployments where API tokens are not
available. The codex subscription CLI handles its own auth via
`codex login`; this provider shells out, pipes the prompt via stdin
(most reliable across platforms for multi-line content), and returns
stdout as the assistant message.

CodexProvider intentionally does NOT try to parse codex CLI's output
format — different versions emit slightly different log preambles. The
agent's own fenced-block extractor finds the ```java...``` block inside
the noise, so we pass stdout through raw.

Everything is configurable without editing this file:

| env var              | meaning                                     | default        |
|----------------------|---------------------------------------------|----------------|
| FORGE_CODEX_BIN      | binary path (e.g. `codex.cmd` on Windows)   | `codex`        |
| FORGE_CODEX_MODEL    | model name passed via --model               | `gpt-5-codex`  |
| FORGE_CODEX_MODEL_FLAG | flag name for the model (set "" to drop)  | `--model`      |
| FORGE_CODEX_SUBCMD   | subcommand (space-separated)                | `exec`         |
| FORGE_CODEX_EXTRA    | extra args before stdin (space-separated)   | (none)         |
| FORGE_CODEX_TIMEOUT  | timeout in seconds                          | `600`          |

A future SDK-based provider should pass the full message array through
so multi-turn tool-use survives. Codex CLI's non-interactive entry
point takes a single prompt, so the message list is flattened here.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field

from forge.llm.provider import CompletionResponse, Message


def _env_tuple(name: str, default: str = "") -> tuple[str, ...]:
    raw = os.environ.get(name, default)
    return tuple(shlex.split(raw)) if raw else ()


@dataclass
class CodexConfig:
    binary: str = field(
        default_factory=lambda: os.environ.get("FORGE_CODEX_BIN", "codex")
    )
    model: str = field(
        default_factory=lambda: os.environ.get("FORGE_CODEX_MODEL", "gpt-5-codex")
    )
    model_flag: str = field(
        default_factory=lambda: os.environ.get("FORGE_CODEX_MODEL_FLAG", "--model")
    )
    subcommand: tuple[str, ...] = field(
        default_factory=lambda: _env_tuple("FORGE_CODEX_SUBCMD", "exec")
    )
    extra_args: tuple[str, ...] = field(
        default_factory=lambda: _env_tuple("FORGE_CODEX_EXTRA")
    )
    timeout_seconds: int = field(
        default_factory=lambda: int(os.environ.get("FORGE_CODEX_TIMEOUT", "600"))
    )


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
        text = self._invoke_codex(prompt)
        # Codex subscription CLI is flat-rate; no per-call cost. Token
        # counts are heuristics — the CLI doesn't expose usage. The
        # cost dashboard treats codex runs as $0 by design.
        return CompletionResponse(
            text=text,
            model=self.model,
            tokens_in=max(1, len(prompt) // 4),
            tokens_out=max(1, len(text) // 4),
            cost_usd=0.0,
        )

    def _invoke_codex(self, prompt: str) -> str:
        binary = shutil.which(self.config.binary) or self.config.binary
        cmd: list[str] = [binary, *self.config.subcommand]
        if self.config.model_flag and self.config.model:
            cmd += [self.config.model_flag, self.config.model]
        cmd += list(self.config.extra_args)

        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.config.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"codex CLI not found at '{self.config.binary}'. "
                f"On Windows set FORGE_CODEX_BIN=codex.cmd (or the full path "
                f"to the npm shim). Original error: {e}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"codex timed out after {self.config.timeout_seconds}s. "
                f"Raise FORGE_CODEX_TIMEOUT or shrink the prompt."
            ) from e

        if result.returncode != 0:
            raise RuntimeError(
                f"codex exited {result.returncode}\n"
                f"  cmd: {' '.join(cmd)}\n"
                f"  stderr: {result.stderr.strip()[:600]}"
            )
        return result.stdout


def _flatten(messages: list[Message]) -> str:
    """Single-prompt flattening for CLI-based providers.

    Single-shot agents send one user message; we pass its content
    through directly so the codex CLI sees exactly the prompt the
    agent rendered. Multi-message conversations (system + user, or
    repair loops) get `[role]` headers so the model can see the
    turn structure.
    """
    if len(messages) == 1 and messages[0].role == "user":
        return messages[0].content
    return "\n\n".join(f"[{m.role}]\n{m.content}" for m in messages)
