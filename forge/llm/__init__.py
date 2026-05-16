"""LLM provider abstraction.

Agents talk to LLMs through the Provider protocol — never call an SDK
directly. This keeps Anthropic/OpenAI/codex/local-model swappable, and
keeps offline test harnesses (EchoProvider) drop-in compatible.
"""

from forge.llm.provider import CompletionResponse, LLMProvider

__all__ = ["CompletionResponse", "LLMProvider"]
