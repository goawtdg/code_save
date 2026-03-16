from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BackendType = Literal["openai", "ollama", "mock"]


class Settings(BaseSettings):
    """Global configuration for safe_codegen."""

    # LLM backends
    backend: BackendType = Field(
        "openai",
        description="LLM backend to use: 'openai', 'ollama', or 'mock'.",
    )
    openai_model: str = Field(
        "gpt-4o-mini",
        description="Default OpenAI model for reasoning and code tasks.",
    )
    openai_base_url: str | None = Field(
        None,
        description="Custom API base URL (e.g. Zhipu https://open.bigmodel.cn/api/paas/v4, DeepSeek https://api.deepseek.com).",
    )
    ollama_model: str = Field(
        "llama3",
        description="Default Ollama model name when using local backend.",
    )

    # 可选第二后端：基座 Layer1 安全审计 + 最后验收 Layer3 由该模型负责（双模型/验收模型）
    validation_backend: BackendType | None = Field(
        None,
        description="If set: Layer1 SecurityAuditor uses this backend (dual-model foundation); Layer3 uses it as primary acceptance (completeness, usability, security compliance).",
    )
    openai_validation_model: str = Field(
        "gpt-4o-mini",
        description="OpenAI model used when validation_backend is 'openai'.",
    )
    validation_base_url: str | None = Field(
        None,
        description="Custom API base URL for validation backend (e.g. DeepSeek https://api.deepseek.com).",
    )
    validation_api_key: str | None = Field(
        default=None,
        description="API key for validation backend; set via SAFE_CODEGEN_VALIDATION_API_KEY in .env.",
    )

    # Thresholds
    foundation_threshold: float = Field(
        0.90, ge=0.0, le=1.0, description="Layer 1 foundation acceptance threshold."
    )
    module_threshold: float = Field(
        0.85, ge=0.0, le=1.0, description="Layer 2 module acceptance threshold."
    )
    global_threshold: float = Field(
        0.70, ge=0.0, le=1.0, description="Layer 3 global convergence threshold."
    )
    max_module_retries: int = Field(
        3, ge=0, description="Maximum retries for Layer 2 self-correction loop."
    )

    # Paths
    data_dir: str = Field(
        "data",
        description="Base directory for foundation and incremental cache data.",
    )

    # API key: read from OPENAI_API_KEY (no prefix) or SAFE_CODEGEN_OPENAI_API_KEY
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI (or Zhipu/DeepSeek) API key; set via OPENAI_API_KEY in .env.",
        validation_alias="OPENAI_API_KEY",
    )

    model_config = SettingsConfigDict(
        env_prefix="SAFE_CODEGEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore other .env keys like OPENAI_API_KEY if not declared
    )


# Demo-mode thresholds when using mock backend so the full pipeline can complete.
_MOCK_THRESHOLD = 0.6


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance.
    When backend is 'mock', thresholds are lowered so the demo run completes.
    """
    s = Settings()
    if s.backend == "mock":
        s.foundation_threshold = _MOCK_THRESHOLD
        s.module_threshold = _MOCK_THRESHOLD
        s.global_threshold = _MOCK_THRESHOLD
    return s

