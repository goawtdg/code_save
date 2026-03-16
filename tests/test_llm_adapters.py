from __future__ import annotations

import os

from safe_codegen.llm import BaseLLMClient, get_llm_client


def test_mock_backend_is_used() -> None:
    os.environ["SAFE_CODEGEN_BACKEND"] = "mock"

    client = get_llm_client()
    assert isinstance(client, BaseLLMClient)

    result = client.generate_text("Hello, world.")
    assert "[MOCK LLM]" in result.content
    assert result.raw is not None

