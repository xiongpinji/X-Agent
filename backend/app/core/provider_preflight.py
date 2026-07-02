from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from backend.app.core.creative_studio.adapters import LOCAL_VIDEO_PROVIDER_NAMES
from backend.app.core.provider_governance_policy import DEEPSEEK_BASE_URL_HOSTS
from backend.app.core.provider_governance_policy import DEFAULT_DEEPSEEK_BASE_URL
from backend.app.core.provider_governance_policy import PROTOCOL_LLM_DENIED_HOSTS
from backend.app.core.provider_governance_policy import PROTOCOL_SEARCH_DENIED_HOSTS
from backend.app.core.url_safety import external_https_url_error_reason

PROVIDER_STATUSES = {"ready_to_call", "missing_config", "rejected_config", "verification_only"}


def build_provider_preflight() -> list[dict[str, Any]]:
    protocol_llm_url = os.environ.get("XAGENT_PROTOCOL_LLM_BASE_URL", "")
    protocol_llm_missing = [
        key
        for key in ("XAGENT_PROTOCOL_LLM_API_KEY", "XAGENT_PROTOCOL_LLM_BASE_URL")
        if not os.environ.get(key)
    ]
    protocol_llm_rejection = "" if protocol_llm_missing else _url_preflight(
        protocol_llm_url,
        denied_hosts=PROTOCOL_LLM_DENIED_HOSTS,
    )

    deepseek_url = os.environ.get("XAGENT_DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL
    deepseek_missing = [key for key in ("XAGENT_DEEPSEEK_API_KEY",) if not os.environ.get(key)]
    deepseek_rejection = "" if deepseek_missing else _url_preflight(
        deepseek_url,
        allowed_hosts=DEEPSEEK_BASE_URL_HOSTS,
    )

    protocol_search_url = os.environ.get("XAGENT_PROTOCOL_SEARCH_BASE_URL", "")
    protocol_search_missing = [
        key
        for key in ("XAGENT_PROTOCOL_SEARCH_API_KEY", "XAGENT_PROTOCOL_SEARCH_BASE_URL")
        if not os.environ.get(key)
    ]
    protocol_search_rejection = "" if protocol_search_missing else _url_preflight(
        protocol_search_url,
        denied_hosts=PROTOCOL_SEARCH_DENIED_HOSTS,
    )

    creative_provider = os.environ.get("XAGENT_CREATIVE_VIDEO_PROVIDER", "external-video-api")
    creative_url = os.environ.get("XAGENT_CREATIVE_VIDEO_API_URL", "")
    creative_missing = [
        key
        for key in ("XAGENT_CREATIVE_VIDEO_API_KEY", "XAGENT_CREATIVE_VIDEO_API_URL")
        if not os.environ.get(key)
    ]
    creative_rejection = ""
    if creative_provider.strip().lower() in LOCAL_VIDEO_PROVIDER_NAMES:
        creative_rejection = "provider must not be local"
    elif not creative_missing:
        creative_rejection = _url_preflight(creative_url)

    return [
        {
            "capability": "llm",
            "provider": "protocol-llm",
            "status": _provider_status(missing=protocol_llm_missing, rejection_reason=protocol_llm_rejection),
            "missing_config": protocol_llm_missing,
            "configuration_error": protocol_llm_rejection,
            "base_url_configured": bool(protocol_llm_url),
            "api_key_configured": _configured("XAGENT_PROTOCOL_LLM_API_KEY"),
            "api_key_fingerprint": _fingerprint_env("XAGENT_PROTOCOL_LLM_API_KEY"),
            "external_https_required": True,
            "official_hosts_blocked": sorted(PROTOCOL_LLM_DENIED_HOSTS),
            "network_call_attempted": False,
        },
        {
            "capability": "llm",
            "provider": "deepseek",
            "status": _provider_status(missing=deepseek_missing, rejection_reason=deepseek_rejection),
            "missing_config": deepseek_missing,
            "configuration_error": deepseek_rejection,
            "base_url_configured": bool(os.environ.get("XAGENT_DEEPSEEK_BASE_URL")),
            "api_key_configured": _configured("XAGENT_DEEPSEEK_API_KEY"),
            "api_key_fingerprint": _fingerprint_env("XAGENT_DEEPSEEK_API_KEY"),
            "official_host_only": True,
            "allowed_hosts": sorted(DEEPSEEK_BASE_URL_HOSTS),
            "network_call_attempted": False,
        },
        {
            "capability": "rag",
            "provider": "protocol-search",
            "status": _provider_status(missing=protocol_search_missing, rejection_reason=protocol_search_rejection),
            "missing_config": protocol_search_missing,
            "configuration_error": protocol_search_rejection,
            "base_url_configured": bool(protocol_search_url),
            "api_key_configured": _configured("XAGENT_PROTOCOL_SEARCH_API_KEY"),
            "api_key_fingerprint": _fingerprint_env("XAGENT_PROTOCOL_SEARCH_API_KEY"),
            "external_https_required": True,
            "official_hosts_blocked": sorted(PROTOCOL_SEARCH_DENIED_HOSTS),
            "network_call_attempted": False,
        },
        {
            "capability": "creative-video",
            "provider": creative_provider,
            "status": _provider_status(missing=creative_missing, rejection_reason=creative_rejection),
            "missing_config": creative_missing,
            "configuration_error": creative_rejection,
            "base_url_configured": bool(creative_url),
            "api_key_configured": _configured("XAGENT_CREATIVE_VIDEO_API_KEY"),
            "api_key_fingerprint": _fingerprint_env("XAGENT_CREATIVE_VIDEO_API_KEY"),
            "external_https_required": True,
            "requires_human_review": True,
            "network_call_attempted": False,
        },
        {
            "capability": "llm+rag",
            "provider": "mock",
            "status": "verification_only",
            "missing_config": [],
            "configuration_error": "",
            "api_key_configured": False,
            "api_key_fingerprint": "",
            "network_call_attempted": False,
        },
    ]


def _configured(env_key: str) -> bool:
    return bool(os.environ.get(env_key))


def _fingerprint_env(env_key: str) -> str:
    value = os.environ.get(env_key, "")
    if not value:
        return ""
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").rstrip(".").lower()


def _url_preflight(url: str, *, denied_hosts: set[str] | None = None, allowed_hosts: set[str] | None = None) -> str:
    error = external_https_url_error_reason(url)
    if error is not None:
        return error
    host = _host(url)
    if denied_hosts and host in denied_hosts:
        return "host is blocked for this protocol gateway"
    if allowed_hosts and host not in allowed_hosts:
        return "host is not allowed for this provider"
    return ""


def _provider_status(*, missing: list[str], rejection_reason: str = "", verification_only: bool = False) -> str:
    if verification_only:
        return "verification_only"
    if rejection_reason:
        return "rejected_config"
    if missing:
        return "missing_config"
    return "ready_to_call"
