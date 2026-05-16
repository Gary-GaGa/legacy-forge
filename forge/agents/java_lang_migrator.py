"""Java Lang Migrator — the first concrete agent.

Scope: Java 7 idioms -> Java 17/21 idioms, behaviour-preserving language
rewrites only. Namespace migration (javax->jakarta) and framework upgrades
live in separate agents.

Exercises all seven pillars end-to-end:
1. Context Engineering — prompt loaded from prompts/java-lang-migrator/v1.md
2. Tool Ergonomics     — pydantic Input/Output schemas
3. Evals               — see evals/cases/java-lang-migrator/
4. Observability       — emits agent + llm spans into the tracer
5. Sandbox             — read-only here; worktree owner-of-record for
                         `forge agent run` (not yet implemented)
6. Orchestration       — budget tick after every LLM round-trip
7. Provenance          — write_trail() on outputs targeted at real files
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from forge.agents.base import Agent, AgentContext
from forge.llm.provider import LLMProvider
from forge.prompt import Prompt, load_prompt, render


class JavaLangMigratorInput(BaseModel):
    source_path: str
    source_code: str
    target_java: int = Field(default=21, ge=8, le=24)


class JavaLangMigratorOutput(BaseModel):
    migrated_code: str
    review_notes: list[str] = Field(default_factory=list)
    model: str
    prompt_version: str


class JavaLangMigrator(Agent[JavaLangMigratorInput, JavaLangMigratorOutput]):
    name = "java-lang-migrator"
    Input = JavaLangMigratorInput
    Output = JavaLangMigratorOutput

    def __init__(
        self,
        provider: LLMProvider,
        *,
        prompts_dir: Path,
        prompt_version: str = "v1",
    ):
        self.provider = provider
        self.prompt_version = prompt_version
        self._prompts_dir = prompts_dir
        self._prompt_cache: Prompt | None = None

    def _prompt(self) -> Prompt:
        if self._prompt_cache is None:
            self._prompt_cache = load_prompt(
                self.name, self.prompt_version, prompts_dir=self._prompts_dir
            )
        return self._prompt_cache

    def run(
        self, ctx: AgentContext, inp: JavaLangMigratorInput
    ) -> JavaLangMigratorOutput:
        prompt = self._prompt()
        rendered = render(
            prompt,
            target_java=inp.target_java,
            source_path=inp.source_path,
            source_code=inp.source_code,
        )

        with ctx.tracer.span(
            "agent",
            self.name,
            run_id=ctx.run_id,
            attrs={
                "prompt_version": self.prompt_version,
                "target_java": str(inp.target_java),
                "source_path": inp.source_path,
            },
        ) as agent_span:
            with ctx.tracer.span(
                "llm",
                "complete",
                run_id=ctx.run_id,
                parent_id=agent_span.span_id,
            ) as llm_span:
                resp = self.provider.complete(
                    rendered, max_tokens=prompt.meta.max_tokens
                )
                llm_span.model = resp.model
                llm_span.tokens_in = resp.tokens_in
                llm_span.tokens_out = resp.tokens_out
                llm_span.cache_read = resp.cache_read
                llm_span.cache_write = resp.cache_write
                llm_span.cost_usd = resp.cost_usd
                ctx.tracer.record_payload(llm_span.span_id, "prompt", rendered)
                ctx.tracer.record_payload(llm_span.span_id, "response", resp.text)

            ctx.budget.tick(
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                cache_read=resp.cache_read,
                dollars=resp.cost_usd,
            )
            ctx.budget.bail_if_exhausted()

            migrated = extract_java_block(resp.text) or inp.source_code
            notes = extract_review_notes(migrated)
            return JavaLangMigratorOutput(
                migrated_code=migrated,
                review_notes=notes,
                model=resp.model,
                prompt_version=self.prompt_version,
            )


_FENCE_JAVA = re.compile(r"```(?:java)?\n(.*?)\n```", re.DOTALL)
_REVIEW_RE = re.compile(r"//\s*FORGE-REVIEW:\s*(.*)")


def extract_java_block(text: str) -> str | None:
    matches = _FENCE_JAVA.findall(text)
    return matches[-1] if matches else None


def extract_review_notes(code: str) -> list[str]:
    return [m.group(1).strip() for m in _REVIEW_RE.finditer(code)]
