from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any


SUPPORTED_MODEL_PROVIDERS = ("openai", "deepseek", "ollama")
DEFAULT_REQUIRED_MODEL_PROVIDERS = ("openai",)
REQUIRED_MODEL_PROVIDERS_ENV = "XAGENT_REQUIRED_MODEL_PROVIDERS"

CANONICAL_PROVIDER_REQUIRED_ENV_VARS = {
    "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "ollama": (),
}

OPENAI_COMPATIBLE_API_KEY_ENV_VARS = (
    "OPENAI_API_KEY",
    "XAGENT_OPENAI_API_KEY",
    "XAGENT_LLM_API_KEY",
)
OPENAI_COMPATIBLE_BASE_URL_ENV_VARS = (
    "OPENAI_BASE_URL",
    "XAGENT_OPENAI_BASE_URL",
    "XAGENT_LLM_BASE_URL",
)
OPENAI_COMPATIBLE_MODEL_ENV_VARS = (
    "OPENAI_MODEL",
    "XAGENT_OPENAI_MODEL",
    "XAGENT_LLM_MODEL",
)
DEEPSEEK_API_KEY_ENV_VARS = (
    "DEEPSEEK_API_KEY",
    "XAGENT_DEEPSEEK_API_KEY",
    "XAGENT_LLM_API_KEY",
)

PROVIDER_ENV_VAR_ALIASES = {
    "openai": (
        *OPENAI_COMPATIBLE_API_KEY_ENV_VARS,
        *OPENAI_COMPATIBLE_BASE_URL_ENV_VARS,
        *OPENAI_COMPATIBLE_MODEL_ENV_VARS,
    ),
    "deepseek": DEEPSEEK_API_KEY_ENV_VARS,
    "ollama": (),
}

ALL_PROVIDER_ENV_VARS = tuple(
    dict.fromkeys(env_var for values in PROVIDER_ENV_VAR_ALIASES.values() for env_var in values)
)

STALE_PROVIDER_NEXT_ACTIONS = (
    "Set OPENAI_API_KEY and OPENAI_BASE_URL/OPENAI_API_FORMAT when using an "
    "OpenAI-compatible endpoint; rerun scripts/run_remote_provider_evidence.py --strict.",
    "Set OPENAI_API_KEY, OPENAI_BASE_URL, and OPENAI_MODEL (plus OPENAI_API_FORMAT when "
    "needed) when using an OpenAI-compatible endpoint, then regenerate remote provider evidence.",
    "Set OPENAI_API_KEY, OPENAI_BASE_URL, and OPENAI_MODEL (plus OPENAI_API_FORMAT when "
    "needed) when using an OpenAI-compatible endpoint; rerun scripts/run_remote_provider_evidence.py --strict.",
    "Set required provider credentials, OPENAI_BASE_URL, OPENAI_MODEL, and OPENAI_API_FORMAT when "
    "using an OpenAI-compatible endpoint; rerun strict provider smoke.",
)


def normalize_required_model_providers(
    providers: Sequence[str] | None,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    if providers is None:
        runtime_env = os.environ if env is None else env
        raw_providers = _split_env_providers(runtime_env.get(REQUIRED_MODEL_PROVIDERS_ENV, ""))
        providers = raw_providers or DEFAULT_REQUIRED_MODEL_PROVIDERS

    normalized: list[str] = []
    for raw_provider in providers:
        provider = str(raw_provider).strip().lower()
        if not provider:
            continue
        if provider not in SUPPORTED_MODEL_PROVIDERS:
            raise ValueError(
                f"Unsupported required model provider: {raw_provider}. "
                f"Use one of: {', '.join(SUPPORTED_MODEL_PROVIDERS)}."
            )
        if provider not in normalized:
            normalized.append(provider)
    if not normalized:
        raise ValueError("At least one required model provider must be configured.")
    return tuple(normalized)


def canonical_required_env_vars_for_providers(
    providers: Sequence[str] | None,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    names: list[str] = []
    for provider in normalize_required_model_providers(providers, env=env):
        for name in CANONICAL_PROVIDER_REQUIRED_ENV_VARS.get(provider, ()):
            if name not in names:
                names.append(name)
    return tuple(names)


def canonicalize_provider_required_env_vars(
    values: Sequence[str] | None,
    *,
    providers: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    names: list[str] = []
    canonical_inserted = False

    def add_canonical_provider_names() -> None:
        nonlocal canonical_inserted
        if canonical_inserted:
            return
        for name in canonical_required_env_vars_for_providers(providers, env=env):
            if name not in names:
                names.append(name)
        canonical_inserted = True

    for raw_value in values or ():
        name = str(raw_value).strip()
        if not name:
            continue
        if name in ALL_PROVIDER_ENV_VARS:
            add_canonical_provider_names()
            continue
        if name not in names:
            names.append(name)

    if providers is not None:
        add_canonical_provider_names()
    return tuple(names)


def provider_env_contracts_for_providers(
    providers: Sequence[str] | None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    runtime_env = os.environ if env is None else env
    contracts: list[dict[str, Any]] = []
    for provider in normalize_required_model_providers(providers, env=runtime_env):
        if provider == "openai":
            contracts.append(
                {
                    "provider": "openai",
                    "provider_slot": "openai_compatible_protocol",
                    "display_name": "OpenAI-compatible protocol provider",
                    "required": True,
                    "protocol": "openai_compatible",
                    "endpoint_requirement": "explicit_openai_compatible_base_url",
                    "official_endpoint_required": False,
                    "official_provider_required": False,
                    "canonical_required_env_vars": ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"],
                    "api_key_env_vars": list(OPENAI_COMPATIBLE_API_KEY_ENV_VARS),
                    "base_url_env_vars": list(OPENAI_COMPATIBLE_BASE_URL_ENV_VARS),
                    "model_env_vars": list(OPENAI_COMPATIBLE_MODEL_ENV_VARS),
                    "optional_env_vars": ["OPENAI_API_FORMAT"],
                    "api_key_present": _any_env_present(runtime_env, OPENAI_COMPATIBLE_API_KEY_ENV_VARS),
                    "base_url_present": _any_env_present(runtime_env, OPENAI_COMPATIBLE_BASE_URL_ENV_VARS),
                    "model_present": _any_env_present(runtime_env, OPENAI_COMPATIBLE_MODEL_ENV_VARS),
                }
            )
        elif provider == "deepseek":
            contracts.append(
                {
                    "provider": "deepseek",
                    "provider_slot": "deepseek_native_api",
                    "display_name": "DeepSeek native API provider",
                    "required": True,
                    "protocol": "provider_native_api",
                    "endpoint_requirement": "provider_native_default_or_configured_base_url",
                    "official_endpoint_required": False,
                    "official_provider_required": False,
                    "canonical_required_env_vars": ["DEEPSEEK_API_KEY"],
                    "api_key_env_vars": list(DEEPSEEK_API_KEY_ENV_VARS),
                    "base_url_env_vars": [],
                    "optional_env_vars": [],
                    "api_key_present": _any_env_present(runtime_env, DEEPSEEK_API_KEY_ENV_VARS),
                    "base_url_present": True,
                }
            )
        elif provider == "ollama":
            contracts.append(
                {
                    "provider": "ollama",
                    "provider_slot": "local_ollama",
                    "display_name": "Local Ollama provider",
                    "required": True,
                    "protocol": "local_ollama",
                    "endpoint_requirement": "local_or_configured_ollama_base_url",
                    "official_endpoint_required": False,
                    "official_provider_required": False,
                    "canonical_required_env_vars": [],
                    "api_key_env_vars": [],
                    "base_url_env_vars": [],
                    "optional_env_vars": [],
                    "api_key_present": True,
                    "base_url_present": True,
                }
            )
    return contracts


def missing_required_provider_env(
    providers: Sequence[str] | None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for contract in provider_env_contracts_for_providers(providers, env=env):
        if contract["provider"] == "openai":
            if not contract["api_key_present"]:
                missing.append({"provider": "openai", "field": "api_key", "env_vars": contract["api_key_env_vars"]})
            if not contract["base_url_present"]:
                missing.append({"provider": "openai", "field": "base_url", "env_vars": contract["base_url_env_vars"]})
            if not contract["model_present"]:
                missing.append({"provider": "openai", "field": "model", "env_vars": contract["model_env_vars"]})
        elif contract["provider"] == "deepseek" and not contract["api_key_present"]:
            missing.append({"provider": "deepseek", "field": "api_key", "env_vars": contract["api_key_env_vars"]})
    return missing


def is_stale_provider_next_action(value: str) -> bool:
    return str(value or "").strip() in STALE_PROVIDER_NEXT_ACTIONS


def _split_env_providers(raw_env: str) -> tuple[str, ...]:
    values = [
        item.strip()
        for chunk in str(raw_env or "").replace(";", ",").split(",")
        for item in chunk.split()
        if item.strip()
    ]
    return tuple(values)


def _any_env_present(env: Mapping[str, str], names: Sequence[str]) -> bool:
    return any(bool(str(env.get(name, "")).strip()) for name in names)
