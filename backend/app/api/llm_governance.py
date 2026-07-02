from __future__ import annotations

import time
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import XAgentAPIError, api_error
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import ErrorCode
from backend.app.core.llm import LLMBackendError, LLMResponse, build_llm_router
from backend.app.core.llm.cost_optimizer import CostTracker, TokenEstimator
from backend.app.core.provider_governance_policy import DEEPSEEK_BASE_URL_HOSTS
from backend.app.core.provider_governance_policy import DEFAULT_DEEPSEEK_BASE_URL
from backend.app.core.provider_governance_policy import PROTOCOL_LLM_DENIED_HOSTS
from backend.app.core.security import Principal
from backend.app.core.url_safety import external_https_url_error_reason
from backend.app.dependencies import (
    enforce_scope,
    get_audit_store,
    get_current_principal,
    get_llm_cost_tracker,
)
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/llm", tags=["llm-governance"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
CostTrackerDependency = Annotated[CostTracker, Depends(get_llm_cost_tracker)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]

SUPPORTED_PROVIDERS = {"protocol-llm", "deepseek", "mock", "auto"}
COMPLETION_PROVIDERS = {"protocol-llm", "deepseek", "mock"}
LOCAL_PROVIDER_NAMES = {"ollama", "local", "localhost", "comfyui"}


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str = Field(..., min_length=1, max_length=20_000)


class LLMCompletionRequest(BaseModel):
    messages: list[LLMMessage] = Field(..., min_length=1, max_length=32)
    provider: str | None = Field(default=None, max_length=32)
    max_output_tokens: int = Field(default=1024, ge=1, le=4096)
    max_input_tokens: int | None = Field(default=None, ge=1, le=200_000)
    max_estimated_cost_usd: float | None = Field(default=None, ge=0, le=1000)
    task_type: str = Field(default="general", max_length=64)


class LLMUsage(BaseModel):
    input_tokens_estimated: int
    output_tokens_estimated: int
    total_tokens_estimated: int
    tokens_used: int
    cost_usd: float
    latency_ms: float


class LLMCompletionResponse(BaseModel):
    content: str
    provider: str
    model: str
    usage: LLMUsage
    governance: dict[str, object]


def _requested_provider(provider: str | None) -> str:
    settings = get_settings()
    value = (provider or settings.llm_backend or "mock").strip().lower()
    if value in LOCAL_PROVIDER_NAMES:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Local model providers are not supported by this API-only route.",
            details={"provider": value, "supported_providers": sorted(SUPPORTED_PROVIDERS - {"auto"})},
        )
    if value not in SUPPORTED_PROVIDERS:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Unsupported LLM provider.",
            details={"provider": value, "supported_providers": sorted(SUPPORTED_PROVIDERS)},
        )
    return value


def _completion_provider(provider: str | None) -> str:
    value = _requested_provider(provider)
    if value == "auto":
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Auto provider routing is not enabled for governed completion requests.",
            details={"provider": value, "supported_providers": sorted(COMPLETION_PROVIDERS)},
        )
    if value == "mock" and not _mock_provider_enabled():
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Mock LLM provider is reserved for deterministic verification and is disabled by default.",
            details={"provider": value, "enable_with": "XAGENT_ENABLE_API_MOCK_PROVIDER=true"},
        )
    return value


def _fallback_order_for(provider: str) -> str:
    settings = get_settings()
    if provider == "auto":
        configured = [
            item.strip().lower()
            for item in settings.llm_fallback_order.split(",")
            if item.strip()
        ]
        external_only = [
            item
            for item in configured
            if item in {"protocol-llm", "deepseek"} and item not in LOCAL_PROVIDER_NAMES
        ]
        if _mock_provider_enabled() and "mock" in configured:
            external_only.append("mock")
        return ",".join(external_only or ["protocol-llm", "deepseek"])
    return provider


def _mock_provider_enabled() -> bool:
    return bool(get_settings().enable_api_mock_provider)


def _provider_configured(provider: str) -> bool:
    settings = get_settings()
    if provider == "mock":
        return _mock_provider_enabled()
    if provider == "protocol-llm":
        return bool(settings.protocol_llm_api_key and settings.protocol_llm_base_url)
    if provider == "deepseek":
        return bool(settings.deepseek_api_key)
    if provider == "auto":
        return bool(
            (settings.protocol_llm_api_key and settings.protocol_llm_base_url)
            or settings.deepseek_api_key
        )
    return False


def _estimate_tokens(request: LLMCompletionRequest) -> tuple[int, int]:
    input_tokens = sum(TokenEstimator.estimate_input_tokens(item.content) for item in request.messages)
    output_tokens = request.max_output_tokens
    return input_tokens, output_tokens


def _estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    if provider == "mock":
        return 0.0
    # Conservative per-1K estimates; final accounting uses provider-reported response.cost.
    pricing = {
        "protocol-llm": {"prompt": 0.005, "completion": 0.015},
        "deepseek": {"prompt": 0.00027, "completion": 0.00110},
    }
    rates = pricing.get(provider, {"prompt": 0.0, "completion": 0.0})
    return (input_tokens * rates["prompt"] + output_tokens * rates["completion"]) / 1000


def _provider_model(provider: str) -> str:
    settings = get_settings()
    if provider == "deepseek":
        return settings.deepseek_model
    if provider == "protocol-llm":
        return settings.protocol_llm_model
    return "mock"


def _protocol_llm_base_url(provider: str) -> str | None:
    if provider != "protocol-llm":
        return None
    settings = get_settings()
    base_url = settings.protocol_llm_base_url
    error = external_https_url_error_reason(base_url)
    if error is not None:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Protocol LLM base URL must be an external HTTPS endpoint.",
            details={"provider": "protocol-llm", "reason": error},
        )
    host = (urlparse(base_url).hostname or "").rstrip(".").lower()
    if host in PROTOCOL_LLM_DENIED_HOSTS:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Protocol LLM base URL must use a protocol-compatible gateway, not the official OpenAI API host.",
            details={"provider": "protocol-llm", "denied_hosts": sorted(PROTOCOL_LLM_DENIED_HOSTS)},
        )
    return base_url


def _deepseek_base_url(provider: str) -> str | None:
    if provider != "deepseek":
        return None
    settings = get_settings()
    base_url = settings.deepseek_base_url or DEFAULT_DEEPSEEK_BASE_URL
    error = external_https_url_error_reason(base_url)
    if error is not None:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "DeepSeek base URL must be an external HTTPS endpoint.",
            details={"provider": "deepseek", "reason": error},
        )
    host = (urlparse(base_url).hostname or "").rstrip(".").lower()
    if host not in DEEPSEEK_BASE_URL_HOSTS:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "DeepSeek base URL must use the official DeepSeek API host.",
            details={"provider": "deepseek", "allowed_hosts": sorted(DEEPSEEK_BASE_URL_HOSTS)},
        )
    return base_url


def _budget_guard(
    request: LLMCompletionRequest,
    *,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
) -> None:
    settings = get_settings()
    token_budget = request.max_input_tokens or settings.default_token_budget
    cost_budget = (
        request.max_estimated_cost_usd
        if request.max_estimated_cost_usd is not None
        else settings.default_cost_budget_usd
    )

    if input_tokens > token_budget:
        raise api_error(
            429,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            "Estimated input token budget exceeded.",
            details={
                "provider": provider,
                "input_tokens_estimated": input_tokens,
                "input_token_budget": token_budget,
            },
        )

    if estimated_cost_usd > cost_budget:
        raise api_error(
            429,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            "Estimated LLM cost budget exceeded.",
            details={
                "provider": provider,
                "estimated_cost_usd": round(estimated_cost_usd, 8),
                "cost_budget_usd": cost_budget,
                "output_tokens_estimated": output_tokens,
            },
        )


def _record_audit(
    audit_store: AuditStore,
    principal: Principal,
    *,
    provider: str,
    model: str,
    outcome: str,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    error_code: str | None = None,
) -> None:
    audit_store.record(
        action="llm.completion",
        resource_type="llm_provider",
        resource_id=provider,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        outcome=outcome,
        trace_id=principal.trace_id,
        details={
            "provider": provider,
            "model": model,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
            "error_code": error_code,
        },
    )


def _record_cost(
    cost_tracker: CostTracker,
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    success: bool,
    latency_ms: float,
    task_type: str,
    principal: Principal,
) -> None:
    cost_tracker.record_call(
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        success=success,
        latency_ms=latency_ms,
        task_type=task_type,
        user_id=principal.user_id,
        session_id=principal.session_id,
    )


@router.get("/providers")
async def list_llm_providers(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    settings = get_settings()
    return {
        "providers": [
            {
                "provider": "protocol-llm",
                "model": settings.protocol_llm_model,
                "configured": bool(settings.protocol_llm_api_key and settings.protocol_llm_base_url),
                "api_only": True,
                "local": False,
                "external_https_required": True,
                "official_hosts_blocked": sorted(PROTOCOL_LLM_DENIED_HOSTS),
            },
            {
                "provider": "deepseek",
                "model": settings.deepseek_model,
                "configured": bool(settings.deepseek_api_key),
                "api_only": True,
                "local": False,
            },
            {
                "provider": "mock",
                "model": "mock",
                "configured": _mock_provider_enabled(),
                "api_only": True,
                "local": False,
                "verification_only": True,
                "enabled_by": "XAGENT_ENABLE_API_MOCK_PROVIDER",
            },
        ],
        "local_providers_blocked": sorted(LOCAL_PROVIDER_NAMES),
        "default_provider": _requested_provider(None),
    }


@router.post("/complete", response_model=LLMCompletionResponse)
async def complete(
    request: LLMCompletionRequest,
    principal: PrincipalDependency,
    cost_tracker: CostTrackerDependency,
    audit_store: AuditStoreDependency,
) -> LLMCompletionResponse:
    enforce_scope(principal, "agent:run")
    input_tokens, output_tokens = _estimate_tokens(request)
    try:
        provider = _completion_provider(request.provider)
    except XAgentAPIError:
        rejected_provider = (request.provider or "unknown").strip().lower() or "unknown"
        _record_cost(
            cost_tracker,
            provider=rejected_provider,
            model="unknown",
            input_tokens=input_tokens,
            output_tokens=0,
            cost_usd=0.0,
            success=False,
            latency_ms=0.0,
            task_type=request.task_type,
            principal=principal,
        )
        _record_audit(
            audit_store,
            principal,
            provider=rejected_provider,
            model="unknown",
            outcome="failure",
            error_code="provider_rejected",
        )
        raise

    model = _provider_model(provider)
    estimated_cost = _estimate_cost(provider, model, input_tokens, output_tokens)
    try:
        _budget_guard(
            request,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
        )
    except XAgentAPIError:
        _record_cost(
            cost_tracker,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=0,
            cost_usd=0.0,
            success=False,
            latency_ms=0.0,
            task_type=request.task_type,
            principal=principal,
        )
        _record_audit(
            audit_store,
            principal,
            provider=provider,
            model=model,
            outcome="failure",
            error_code="budget_guard_rejected",
        )
        raise
    if not _provider_configured(provider):
        _record_cost(
            cost_tracker,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=0,
            cost_usd=0.0,
            success=False,
            latency_ms=0.0,
            task_type=request.task_type,
            principal=principal,
        )
        _record_audit(
            audit_store,
            principal,
            provider=provider,
            model=model,
            outcome="failure",
            error_code="provider_not_configured",
        )
        raise api_error(
            503,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Requested LLM provider is not configured.",
            details={"provider": provider, "configured": False},
        )

    settings = get_settings()
    try:
        protocol_llm_base_url = _protocol_llm_base_url("protocol-llm") if provider in {"protocol-llm", "auto"} else None
        deepseek_base_url = _deepseek_base_url(provider)
    except XAgentAPIError:
        _record_cost(
            cost_tracker,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=0,
            cost_usd=0.0,
            success=False,
            latency_ms=0.0,
            task_type=request.task_type,
            principal=principal,
        )
        _record_audit(
            audit_store,
            principal,
            provider=provider,
            model=model,
            outcome="failure",
            error_code="provider_base_url_rejected",
        )
        raise
    llm_router = build_llm_router(
        llm_backend="openai" if provider == "protocol-llm" else provider,
        fallback_order=_fallback_order_for(provider).replace("protocol-llm", "openai"),
        openai_api_key=settings.protocol_llm_api_key,
        openai_model=settings.protocol_llm_model,
        deepseek_api_key=settings.deepseek_api_key,
        deepseek_model=settings.deepseek_model,
        deepseek_base_url=deepseek_base_url or DEFAULT_DEEPSEEK_BASE_URL,
        openai_base_url=protocol_llm_base_url,
        openai_backend_name="protocol-llm",
    )
    messages = [item.model_dump() for item in request.messages]
    start = time.perf_counter()
    try:
        response: LLMResponse = await llm_router.chat(messages, tools=[])
    except LLMBackendError:
        latency_ms = (time.perf_counter() - start) * 1000
        _record_cost(
            cost_tracker,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=0,
            cost_usd=0.0,
            success=False,
            latency_ms=latency_ms,
            task_type=request.task_type,
            principal=principal,
        )
        _record_audit(
            audit_store,
            principal,
            provider=provider,
            model=model,
            outcome="failure",
            error_code="provider_request_failed",
        )
        raise api_error(
            502,
            ErrorCode.INTERNAL_ERROR,
            "LLM provider request failed.",
            details={"provider": provider},
        )

    latency_ms = response.latency_ms or (time.perf_counter() - start) * 1000
    actual_cost = float(response.cost or 0.0)
    tokens_used = int(response.tokens_used or 0)
    _record_cost(
        cost_tracker,
        model=response.model or model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=max(0, tokens_used - input_tokens),
        cost_usd=actual_cost,
        success=True,
        latency_ms=latency_ms,
        task_type=request.task_type,
        principal=principal,
    )
    _record_audit(
        audit_store,
        principal,
        provider=provider,
        model=response.model or model,
        outcome="success",
        tokens_used=tokens_used,
        cost_usd=actual_cost,
    )
    return LLMCompletionResponse(
        content=response.content or "",
        provider=provider,
        model=response.model or model,
        usage=LLMUsage(
            input_tokens_estimated=input_tokens,
            output_tokens_estimated=output_tokens,
            total_tokens_estimated=input_tokens + output_tokens,
            tokens_used=tokens_used,
            cost_usd=actual_cost,
            latency_ms=latency_ms,
        ),
        governance={
            "budget_checked": True,
            "estimated_cost_usd": round(estimated_cost, 8),
            "api_only": True,
            "local_provider_blocked": False,
            "audit_recorded": True,
        },
    )


@router.get("/stats")
async def llm_stats(
    principal: PrincipalDependency,
    cost_tracker: CostTrackerDependency,
) -> dict[str, object]:
    enforce_scope(principal, "audit:read")
    report = cost_tracker.get_report(hours=24)
    return {
        "period_hours": report["period_hours"],
        "total_cost_usd": report["total_cost_usd"],
        "cost_by_model": report["cost_by_model"],
        "cost_by_provider": report["cost_by_provider"],
        "success_rate": report["success_rate"],
        "average_latency_ms": report["average_latency_ms"],
        "api_only": True,
        "local_providers_blocked": sorted(LOCAL_PROVIDER_NAMES),
    }
