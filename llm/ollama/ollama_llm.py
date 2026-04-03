"""Ollama implementation of LLMClient."""

from __future__ import annotations

import ollama


class OllamaLLM:
    def __init__(self, model: str) -> None:
        self.model = model

    def complete(self, *, system: str, user: str) -> str:
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        message = response.message
        content = message.content if message else None
        if not content:
            raise RuntimeError("Ollama returned no assistant content.")
        return content


__all__ = ["OllamaLLM"]
