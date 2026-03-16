from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..config import Settings, get_settings


@dataclass
class LLMResponse:
    """Simple container for LLM outputs."""

    content: str
    raw: Any | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class BaseLLMClient(ABC):
    """Abstract base class for all LLM backends."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    @abstractmethod
    def generate_text(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate text from a prompt."""


class MockLLMClient(BaseLLMClient):
    """Lightweight mock backend used for tests and offline runs."""

    def generate_text(self, prompt: str, **kwargs: Any) -> LLMResponse:
        # Very small deterministic stub, avoids any external calls.
        summary = prompt[:80].replace("\n", " ")
        content = f"[MOCK LLM] summary_of_prompt: {summary}"
        return LLMResponse(content=content, raw={"backend": "mock"})


def get_llm_client(settings: Optional[Settings] = None) -> BaseLLMClient:
    """Factory returning an LLM client based on configuration."""

    cfg = settings or get_settings()

    if cfg.backend == "mock":
        return MockLLMClient(cfg)

    if cfg.backend == "openai":
        from .openai_client import OpenAIClient

        return OpenAIClient(cfg)

    if cfg.backend == "ollama":
        from .ollama_client import OllamaClient

        return OllamaClient(cfg)

    # Fallback to mock for any unknown value to keep the system robust.
    return MockLLMClient(cfg)


def get_validation_client(settings: Optional[Settings] = None) -> BaseLLMClient | None:
    """Return an optional LLM client for cross-validation (e.g. Layer 3).

    If validation_backend is not set, returns None. Otherwise returns a client
    using validation_backend (and validation-specific model if applicable).
    """
    cfg = settings or get_settings()
    if not cfg.validation_backend:
        return None

    overrides: Dict[str, Any] = {
        "backend": cfg.validation_backend,
    }
    if cfg.validation_backend == "openai":
        overrides["openai_model"] = getattr(cfg, "openai_validation_model", "gpt-4o-mini")
        # Allow fully separate base_url and api_key for validation backend.
        if getattr(cfg, "validation_base_url", None):
            overrides["openai_base_url"] = cfg.validation_base_url
        if getattr(cfg, "validation_api_key", None):
            overrides["openai_api_key"] = cfg.validation_api_key

    validation_settings = cfg.model_copy(update=overrides)
    return get_llm_client(validation_settings)

