"""LLM feature settings read directly from the environment (P1-08).

``backend/app/settings.py`` is frozen for this wave, so the new LLM routing
knobs live in this dedicated pydantic-settings submodel. All variables use the
same ``XAGENT_`` prefix as the main settings and also read the project ``.env``.

These settings are consumed by ``build_llm_router`` only; explicit keyword
arguments passed to ``build_llm_router`` always win over these values.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMFeatureSettings(BaseSettings):
    """Environment-backed settings for LLM routing convergence."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="XAGENT_",
    )

    # --- Anthropic provider ---
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-haiku-20241022"
    anthropic_base_url: str | None = None

    # --- Ollama provider (local, no credentials) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # --- Routing mode ---
    # "sequential": production behavior — try backends in fallback order.
    # "smart": reorder backends per request via ModelSelector (task type /
    #          cost / latency), still falling back sequentially.
    llm_routing_mode: str = "sequential"
    # balanced | cost_optimized | performance_optimized | latency_optimized |
    # availability | a_b_test
    llm_smart_strategy: str = "balanced"
    # Override path for config/model_profiles.yaml
    llm_model_profiles_path: str | None = None

    # --- Tenant/user token quota ---
    llm_quota_enabled: bool = False
    llm_quota_period: str = "day"  # day | month | total
    llm_quota_default_tenant_tokens: int = 1_000_000
    llm_quota_default_user_tokens: int = 100_000


@lru_cache
def get_llm_feature_settings() -> LLMFeatureSettings:
    """Cached accessor for LLM feature settings."""
    return LLMFeatureSettings()
