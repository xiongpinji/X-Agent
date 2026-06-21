from __future__ import annotations

import asyncio
import json
from typing import Annotated, Literal
from urllib import request as urllib_request
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import XAgentAPIError, api_error
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.core.url_safety import external_https_url_error_reason
from backend.app.dependencies import enforce_scope, get_audit_store, get_current_principal
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/rag", tags=["rag-governance"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]

SUPPORTED_PROVIDERS = {"protocol-search", "mock"}
LOCAL_PROVIDER_NAMES = {"local", "qdrant", "chroma", "pgvector", "ollama", "comfyui", "localhost"}
PROTOCOL_SEARCH_DENIED_HOSTS = {"api.openai.com", "api.tavily.com"}
PROVIDER_URL_VALIDATION_MESSAGES = {
    "External RAG provider URL must be an external HTTPS endpoint.",
    "Protocol search base URL must be an external HTTPS endpoint.",
    "Protocol search base URL must use a protocol-compatible gateway, not official OpenAI or Tavily API hosts.",
}
MOCK_DOCUMENTS = [
    {
        "document_id": "tenant-1-policy",
        "tenant_id": "tenant-1",
        "title": "Tenant 1 API governance policy",
        "snippet": "Tenant 1 requires external API-only model and retrieval providers.",
        "source_url": "https://docs.x-agent.example/tenant-1/api-governance",
    },
    {
        "document_id": "tenant-2-policy",
        "tenant_id": "tenant-2",
        "title": "Tenant 2 private deployment note",
        "snippet": "Tenant 2 local-only notes must never appear in tenant 1 retrieval.",
        "source_url": "https://docs.x-agent.example/tenant-2/private-note",
    },
]


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2_000)
    provider: str | None = Field(default="mock", max_length=32)
    top_k: int = Field(default=3, ge=1, le=10)
    max_results: int = Field(default=5, ge=1, le=20)
    max_estimated_cost_usd: float | None = Field(default=None, ge=0, le=100)
    tenant_scope: str | None = Field(default=None, max_length=128)
    mode: Literal["search", "answer_context"] = "search"


class RAGDocument(BaseModel):
    document_id: str
    title: str
    snippet: str
    source_url: str
    score: float
    tenant_id: str


class RAGQueryResponse(BaseModel):
    provider: str
    query: str
    results: list[RAGDocument]
    governance: dict[str, object]


def _requested_provider(provider: str | None) -> str:
    value = (provider or "mock").strip().lower()
    if value in LOCAL_PROVIDER_NAMES:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Local retrieval providers are not supported by this API-only route.",
            details={"provider": value, "supported_providers": sorted(SUPPORTED_PROVIDERS)},
        )
    if value not in SUPPORTED_PROVIDERS:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Unsupported RAG provider.",
            details={"provider": value, "supported_providers": sorted(SUPPORTED_PROVIDERS)},
        )
    return value


def _estimate_cost(provider: str, *, top_k: int, max_results: int) -> float:
    if provider == "mock":
        return 0.0
    rates = {
        "protocol-search": 0.001,
    }
    return rates.get(provider, 0.0) * max(top_k, max_results)


def _budget_guard(request: RAGQueryRequest, *, provider: str, estimated_cost_usd: float) -> None:
    cost_budget = request.max_estimated_cost_usd if request.max_estimated_cost_usd is not None else 1.0
    if estimated_cost_usd > cost_budget:
        raise api_error(
            429,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            "Estimated RAG retrieval cost budget exceeded.",
            details={
                "provider": provider,
                "estimated_cost_usd": round(estimated_cost_usd, 8),
                "cost_budget_usd": cost_budget,
            },
        )


def _provider_configured(provider: str) -> bool:
    settings = get_settings()
    if provider == "mock":
        return True
    if provider == "protocol-search":
        return bool(settings.protocol_search_api_key and settings.protocol_search_base_url)
    return False


def _protocol_search_base_url() -> str | None:
    settings = get_settings()
    url = settings.protocol_search_base_url
    if not url:
        return None
    error = external_https_url_error_reason(url)
    if error is not None:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Protocol search base URL must be an external HTTPS endpoint.",
            details={"provider": "protocol-search", "reason": error},
        )
    host = (urlparse(url).hostname or "").rstrip(".").lower()
    if host in PROTOCOL_SEARCH_DENIED_HOSTS:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Protocol search base URL must use a protocol-compatible gateway, not official OpenAI or Tavily API hosts.",
            details={"provider": "protocol-search", "denied_hosts": sorted(PROTOCOL_SEARCH_DENIED_HOSTS)},
        )
    return url


def _record_audit(
    audit_store: AuditStore,
    principal: Principal,
    *,
    provider: str,
    outcome: str,
    result_count: int = 0,
    error_code: str | None = None,
) -> None:
    audit_store.record(
        action="rag.query",
        resource_type="rag_provider",
        resource_id=provider,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        outcome=outcome,
        trace_id=principal.trace_id,
        details={
            "provider": provider,
            "result_count": result_count,
            "error_code": error_code,
        },
    )


def _mock_retrieve(request: RAGQueryRequest, principal: Principal) -> list[RAGDocument]:
    tenant_scope = request.tenant_scope or principal.tenant_id
    if tenant_scope != principal.tenant_id:
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "RAG tenant scope does not match the authenticated tenant.",
            details={"tenant_scope": tenant_scope},
        )

    query_terms = {term.lower() for term in request.query.split() if term.strip()}
    results: list[RAGDocument] = []
    for document in MOCK_DOCUMENTS:
        if document["tenant_id"] != principal.tenant_id:
            continue
        haystack = f"{document['title']} {document['snippet']}".lower()
        score = 0.9 if any(term in haystack for term in query_terms) else 0.5
        results.append(
            RAGDocument(
                document_id=document["document_id"],
                title=document["title"],
                snippet=document["snippet"],
                source_url=document["source_url"],
                score=score,
                tenant_id=document["tenant_id"],
            )
        )
    results.sort(key=lambda item: item.score, reverse=True)
    return results[: min(request.top_k, request.max_results)]


async def _external_retrieve(provider: str, request: RAGQueryRequest, principal: Principal) -> list[RAGDocument]:
    tenant_scope = request.tenant_scope or principal.tenant_id
    if tenant_scope != principal.tenant_id:
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "RAG tenant scope does not match the authenticated tenant.",
            details={"tenant_scope": tenant_scope},
        )
    if provider == "protocol-search":
        return await _protocol_search_retrieve(request, principal)
    raise api_error(
        400,
        ErrorCode.VALIDATION_ERROR,
        "Unsupported RAG provider.",
        details={"provider": provider, "supported_providers": sorted(SUPPORTED_PROVIDERS)},
    )


async def _protocol_search_retrieve(request: RAGQueryRequest, principal: Principal) -> list[RAGDocument]:
    settings = get_settings()
    url = _protocol_search_base_url()
    if not url:
        return []
    payload = {
        "query": request.query,
        "mode": request.mode,
        "model": settings.protocol_search_model,
        "top_k": request.top_k,
        "max_results": min(request.top_k, request.max_results),
    }
    data = await _post_external_json(
        url,
        payload,
        {
            "Authorization": f"Bearer {settings.protocol_search_api_key}",
            "Content-Type": "application/json",
        },
    )
    results = data.get("results") or data.get("documents") if isinstance(data, dict) else []
    documents: list[RAGDocument] = []
    for index, item in enumerate(results if isinstance(results, list) else []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("url") or item.get("source_url") or f"Protocol search result {index + 1}")
        source_url = str(item.get("source_url") or item.get("url") or "")
        snippet = str(item.get("snippet") or item.get("content") or item.get("text") or "")
        score = float(item.get("score") or max(0.0, 0.9 - index * 0.05))
        if not source_url:
            continue
        documents.append(
            RAGDocument(
                document_id=str(item.get("document_id") or item.get("id") or f"protocol-search-{index + 1}"),
                title=title,
                snippet=snippet[:1000],
                source_url=source_url,
                score=score,
                tenant_id=principal.tenant_id,
            )
        )
    return documents[: min(request.top_k, request.max_results)]


async def _post_external_json(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
    error = external_https_url_error_reason(url)
    if error is not None:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "External RAG provider URL must be an external HTTPS endpoint.",
            details={"reason": error},
        )

    def _request() -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(url, data=body, headers=headers, method="POST")
        with urllib_request.urlopen(req, timeout=30.0) as response:
            return dict(json.loads(response.read().decode("utf-8")) or {})

    return await asyncio.to_thread(_request)


@router.get("/providers")
async def list_rag_providers(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    return {
        "providers": [
            {
                "provider": "protocol-search",
                "api_only": True,
                "local": False,
                "configured": _provider_configured("protocol-search"),
                "endpoint": get_settings().protocol_search_base_url,
                "external_https_required": True,
                "official_hosts_blocked": sorted(PROTOCOL_SEARCH_DENIED_HOSTS),
            },
            {"provider": "mock", "api_only": True, "local": False, "configured": True, "verification_only": True},
        ],
        "local_providers_blocked": sorted(LOCAL_PROVIDER_NAMES),
        "default_provider": "mock",
    }


@router.post("/query", response_model=RAGQueryResponse)
async def query_rag(
    request: RAGQueryRequest,
    principal: PrincipalDependency,
    audit_store: AuditStoreDependency,
) -> RAGQueryResponse:
    enforce_scope(principal, "memory:read")
    try:
        provider = _requested_provider(request.provider)
    except XAgentAPIError:
        rejected_provider = (request.provider or "unknown").strip().lower() or "unknown"
        _record_audit(
            audit_store,
            principal,
            provider=rejected_provider,
            outcome="failure",
            error_code="provider_rejected",
        )
        raise

    estimated_cost = _estimate_cost(provider, top_k=request.top_k, max_results=request.max_results)
    try:
        _budget_guard(request, provider=provider, estimated_cost_usd=estimated_cost)
    except XAgentAPIError:
        _record_audit(
            audit_store,
            principal,
            provider=provider,
            outcome="failure",
            error_code="budget_guard_rejected",
        )
        raise

    if not _provider_configured(provider):
        _record_audit(
            audit_store,
            principal,
            provider=provider,
            outcome="failure",
            error_code="provider_not_configured",
        )
        raise api_error(
            503,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Requested RAG provider is not configured.",
            details={"provider": provider, "configured": False},
        )

    try:
        results = _mock_retrieve(request, principal) if provider == "mock" else await _external_retrieve(provider, request, principal)
    except XAgentAPIError as exc:
        error_code = "tenant_scope_rejected"
        if exc.code == ErrorCode.VALIDATION_ERROR and exc.message in PROVIDER_URL_VALIDATION_MESSAGES:
            error_code = "provider_base_url_rejected"
        elif exc.code == ErrorCode.VALIDATION_ERROR:
            error_code = "provider_request_rejected"
        _record_audit(
            audit_store,
            principal,
            provider=provider,
            outcome="failure",
            error_code=error_code,
        )
        raise
    except Exception:
        _record_audit(
            audit_store,
            principal,
            provider=provider,
            outcome="failure",
            error_code="provider_request_failed",
        )
        raise api_error(
            502,
            ErrorCode.INTERNAL_ERROR,
            "RAG provider request failed.",
            details={"provider": provider},
        )
    _record_audit(
        audit_store,
        principal,
        provider=provider,
        outcome="success",
        result_count=len(results),
    )
    return RAGQueryResponse(
        provider=provider,
        query=request.query,
        results=results,
        governance={
            "api_only": True,
            "tenant_scoped": True,
            "budget_checked": True,
            "estimated_cost_usd": round(estimated_cost, 8),
            "local_provider_blocked": False,
            "audit_recorded": True,
        },
    )
