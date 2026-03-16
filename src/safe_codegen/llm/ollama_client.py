from __future__ import annotations

from typing import Any, Optional

try:
    from langchain_community.chat_models import ChatOllama
except Exception:  # pragma: no cover - optional dependency
    ChatOllama = None  # type: ignore[assignment]

from ..config import Settings
from .base import BaseLLMClient, LLMResponse


class OllamaClient(BaseLLMClient):
    """Ollama client using langchain-community."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)
        if ChatOllama is None:  # pragma: no cover - defensive
            raise RuntimeError(
                "ChatOllama is not available. "
                "Install `langchain-community` with Ollama support and ensure Ollama is running."
            )
        self._model = ChatOllama(
            model=self.settings.ollama_model,
            temperature=0.1,
        )

    def generate_text(self, prompt: str, **kwargs: Any) -> LLMResponse:
        result = self._model.invoke(prompt, **kwargs)
        content = result.content if hasattr(result, "content") else str(result)
        return LLMResponse(content=content, raw=result)

