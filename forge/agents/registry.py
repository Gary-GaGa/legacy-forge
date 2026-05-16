"""Agent registry.

Maps agent name -> factory. The CLI looks agents up by name when running
`forge eval run <agent>`. New agents add themselves here so the CLI does
not need a growing if/elif chain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from forge.agents.base import Agent
from forge.agents.java_lang_migrator import JavaLangMigrator
from forge.llm.provider import LLMProvider

AgentFactory = Callable[[LLMProvider, Path], Agent]

_REGISTRY: dict[str, AgentFactory] = {
    "java-lang-migrator": lambda provider, prompts_dir: JavaLangMigrator(
        provider, prompts_dir=prompts_dir
    ),
}


def get(name: str) -> AgentFactory:
    if name not in _REGISTRY:
        raise KeyError(
            f"unknown agent: {name}. Known: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def names() -> list[str]:
    return sorted(_REGISTRY)
