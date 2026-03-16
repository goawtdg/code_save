from __future__ import annotations

import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from ..config import Settings, get_settings
from .base import BaseLLMClient, LLMResponse


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client using langchain-openai."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings)
        cfg = self.settings or get_settings()
        api_key = getattr(cfg, "openai_api_key", None) or os.environ.get("OPENAI_API_KEY")
        kwargs: dict = {
            "model": cfg.openai_model,
            "temperature": 0.1,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if getattr(cfg, "openai_base_url", None):
            kwargs["base_url"] = cfg.openai_base_url
        self._model = ChatOpenAI(**kwargs)

    def generate_text(self, prompt: str, **kwargs: Any) -> LLMResponse:
        messages = [
            ("system", "You are a careful software engineer focusing on safety and correctness."),
            ("user", prompt),
        ]
        result = self._model.invoke(messages, **kwargs)
        content = result.content if hasattr(result, "content") else str(result)
        input_tokens = 0
        output_tokens = 0
        if hasattr(result, "usage_metadata") and result.usage_metadata:
            um = result.usage_metadata
            if isinstance(um, dict):
                input_tokens = int(um.get("input_tokens", 0) or 0)
                output_tokens = int(um.get("output_tokens", 0) or 0)
            else:
                input_tokens = int(getattr(um, "input_tokens", 0) or 0)
                output_tokens = int(getattr(um, "output_tokens", 0) or 0)
        return LLMResponse(
            content=content,
            raw=result,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

