"""
LLM backend adapters for safe_codegen.

This package provides a small abstraction layer over different LLM providers
such as OpenAI and Ollama, plus a lightweight mock backend for tests.
"""

from .base import BaseLLMClient, get_llm_client, get_validation_client

__all__ = ["BaseLLMClient", "get_llm_client", "get_validation_client"]

