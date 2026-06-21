from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import XAgentAPIError, api_error
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_audit_store, get_current_principal

router = APIRouter(prefix="/api/v1/rag", tags=["rag-governance"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]

SUPPORTED_PROVIDERS = {"openai-search", "tavily", "mock"}
LOCAL_PROVIDER_NAMES = {"local", "qdrant", "chroma", "pgvector", "ollama", "comfyui", "localhost"}
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
        "openai-search": 0.002,
        "tavily": 0.001,
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


@router.get("/providers")
async def list_rag_providers(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    return {
        "providers": [
            {"provider": "openai-search", "api_only": True, "local": False, "configured": False},
            {"provider": "tavily", "api_only": True, "local": False, "configured": False},
            {"provider": "mock", "api_only": True, "local": False, "configured": True},
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

    if provider != "mock":
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
        results = _mock_retrieve(request, principal)
    except XAgentAPIError:
        _record_audit(
            audit_store,
            principal,
            provider=provider,
            outcome="failure",
            error_code="tenant_scope_rejected",
        )
        raise
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
