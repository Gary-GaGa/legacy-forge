"""Prompt loader + minimal `{{var}}` renderer.

Pillar 1 (Context Engineering). Prompts live on disk under
`prompts/<agent>/<version>.md`, are loaded by the agent at runtime, and
fill `{{var}}` placeholders via plain string substitution. We avoid
jinja2 / format strings on purpose:
- braces appear naturally in code samples; jinja2 would have to escape
- `f""` would interpret backslashes and `{}` inside the prompt body
- `str.replace` is unambiguous and easy to grep for
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class BudgetCaps(BaseModel):
    """Per-agent budget overrides. Any field left None falls back to the
    global Budget defaults at runtime."""

    max_tokens: int | None = None
    max_dollars: float | None = None
    max_wallclock_s: float | None = None
    max_iterations: int | None = None


class PromptMeta(BaseModel):
    model_hint: str = ""
    temperature: float = 0.0
    max_tokens: int = 4096
    input_schema: str = ""        # dotted path to pydantic class
    output_schema: str = ""
    notes: str = ""
    budget: BudgetCaps = Field(default_factory=BudgetCaps)
    extra: dict = Field(default_factory=dict)


class Prompt(BaseModel):
    agent: str
    version: str
    body: str
    meta: PromptMeta = Field(default_factory=PromptMeta)


def load_prompt(agent: str, version: str, *, prompts_dir: Path) -> Prompt:
    body_path = prompts_dir / agent / f"{version}.md"
    if not body_path.exists():
        raise FileNotFoundError(f"prompt not found: {body_path}")
    body = body_path.read_text(encoding="utf-8")

    meta_path = prompts_dir / agent / f"{version}.meta.yaml"
    if meta_path.exists():
        meta = PromptMeta.model_validate(yaml.safe_load(meta_path.read_text(encoding="utf-8")))
    else:
        meta = PromptMeta()

    return Prompt(agent=agent, version=version, body=body, meta=meta)


def render(prompt: Prompt, **vars: object) -> str:
    out = prompt.body
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", str(v))
    leftover = _unfilled_placeholders(out)
    if leftover:
        raise ValueError(
            f"prompt {prompt.agent}/{prompt.version} has unfilled placeholders: {leftover}"
        )
    return out


def _unfilled_placeholders(text: str) -> list[str]:
    return re.findall(r"\{\{(\w+)\}\}", text)
