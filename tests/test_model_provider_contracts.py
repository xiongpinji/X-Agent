from __future__ import annotations

import pytest

from backend.app.core.model_provider_contracts import (
    REQUIRED_MODEL_PROVIDERS_ENV,
    STALE_PROVIDER_NEXT_ACTIONS,
    canonical_required_env_vars_for_providers,
    canonicalize_provider_required_env_vars,
    is_stale_provider_next_action,
    missing_required_provider_env,
    normalize_required_model_providers,
    provider_env_contracts_for_providers,
)


def test_normalize_required_model_providers_defaults_from_env() -> None:
    assert normalize_required_model_providers(None, env={}) == ("openai",)
    assert normalize_required_model_providers(None, env={REQUIRED_MODEL_PROVIDERS_ENV: "deepseek, ollama"}) == (
        "deepseek",
        "ollama",
    )
    assert normalize_required_model_providers([" OpenAI ", "openai", "DEEPSEEK"]) == ("openai", "deepseek")


def test_normalize_required_model_providers_rejects_empty_and_unsupported() -> None:
    with pytest.raises(ValueError, match="At least one required model provider"):
        normalize_required_model_providers([])
    with pytest.raises(ValueError, match="Unsupported required model provider"):
        normalize_required_model_providers(["anthropic"])


def test_canonical_required_env_vars_for_provider_set() -> None:
    assert canonical_required_env_vars_for_providers(("openai", "deepseek", "ollama")) == (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "DEEPSEEK_API_KEY",
    )


def test_canonicalize_provider_required_env_vars_replaces_aliases_once() -> None:
    assert canonicalize_provider_required_env_vars(
        ["XAGENT_OPENAI_API_KEY", "CUSTOM_ENV", "XAGENT_LLM_API_KEY"],
        providers=("openai",),
    ) == ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "CUSTOM_ENV")


def test_openai_provider_contract_is_protocol_slot_not_official_endpoint() -> None:
    [contract] = provider_env_contracts_for_providers(("openai",), env={})

    assert contract["provider"] == "openai"
    assert contract["provider_slot"] == "openai_compatible_protocol"
    assert contract["display_name"] == "OpenAI-compatible protocol provider"
    assert contract["protocol"] == "openai_compatible"
    assert contract["endpoint_requirement"] == "explicit_openai_compatible_base_url"
    assert contract["official_endpoint_required"] is False
    assert contract["official_provider_required"] is False
    assert contract["canonical_required_env_vars"] == ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"]
    assert contract["api_key_present"] is False
    assert contract["base_url_present"] is False
    assert contract["model_present"] is False


def test_contract_presence_uses_provider_aliases() -> None:
    [openai, deepseek, ollama] = provider_env_contracts_for_providers(
        ("openai", "deepseek", "ollama"),
        env={
            "XAGENT_OPENAI_API_KEY": "key",
            "XAGENT_OPENAI_BASE_URL": "https://llm.test/v1",
            "XAGENT_OPENAI_MODEL": "model",
            "XAGENT_DEEPSEEK_API_KEY": "deepseek-key",
        },
    )

    assert openai["api_key_present"] is True
    assert openai["base_url_present"] is True
    assert openai["model_present"] is True
    assert deepseek["api_key_present"] is True
    assert deepseek["base_url_present"] is True
    assert ollama["api_key_present"] is True
    assert ollama["base_url_present"] is True


def test_missing_required_provider_env_reports_field_groups() -> None:
    missing = missing_required_provider_env(
        ("openai", "deepseek"),
        env={"OPENAI_API_KEY": "key", "OPENAI_BASE_URL": "https://llm.test/v1"},
    )

    assert missing == [
        {"provider": "openai", "field": "model", "env_vars": ["OPENAI_MODEL", "XAGENT_OPENAI_MODEL", "XAGENT_LLM_MODEL"]},
        {
            "provider": "deepseek",
            "field": "api_key",
            "env_vars": ["DEEPSEEK_API_KEY", "XAGENT_DEEPSEEK_API_KEY", "XAGENT_LLM_API_KEY"],
        },
    ]


def test_is_stale_provider_next_action_flags_exact_legacy_wording() -> None:
    for action in STALE_PROVIDER_NEXT_ACTIONS:
        assert is_stale_provider_next_action(action)

    assert not is_stale_provider_next_action(
        "Set OPENAI_API_KEY, OPENAI_BASE_URL, and OPENAI_MODEL; rerun strict provider smoke."
    )
    assert not is_stale_provider_next_action(f"Archived note: {STALE_PROVIDER_NEXT_ACTIONS[0]}")
