"""Abstract LLM interface — implementations live in subpackages (e.g. llm.ollama)."""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Anything that can turn a system + user turn into assistant text."""

    def complete(self, *, system: str, user: str) -> str:
        """Return the assistant reply for the given system and user content."""
        ...


__all__ = ["LLMClient"]
