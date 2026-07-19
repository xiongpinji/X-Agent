from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import ErrorCode, RunContext
from backend.app.core.memory import (
    MemoryConsolidationResult,
    MemoryExportBundle,
    MemoryItem,
    MemoryScope,
    MemorySearchHit,
    MemorySystem,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_audit_store, get_current_principal, get_memory
from backend.app.services.observability.langfuse_client import langfuse_client

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]
MemoryDependency = Annotated[object, Depends(get_memory)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class MemoryStoreRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=20_000)
    layer: int = Field(default=3, ge=1, le=10)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    session_id: str | None = None
    scope: MemoryScope | None = None


class MemoryStoreResponse(BaseModel):
    id: str


class MemorySearchRequest(BaseModel):
    query: str = ""
    layers: list[int] | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    include_scores: bool = False
    scope: MemoryScope | None = None


class MemorySearchResponse(BaseModel):
    items: list[MemoryItem] = Field(default_factory=list)
    hits: list[MemorySearchHit] = Field(default_factory=list)


class MemoryConsolidateRequest(BaseModel):
    source_layers: list[int] | None = None
    target_layer: int = Field(default=4, ge=1, le=10)
    max_items: int = Field(default=20, ge=1, le=100)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)


class MemoryExportResponse(BaseModel):
    bundle: MemoryExportBundle


class MemoryImportResponse(BaseModel):
    memories: int
    sessions: int


@router.post("", response_model=MemoryStoreResponse)
async def store_memory(request: MemoryStoreRequest, memory: MemoryDependency, audit_store: AuditStoreDependency, principal: PrincipalDependency) -> MemoryStoreResponse:
    enforce_scope(principal, "memory:write")
    context = _context_from_principal(principal)
    memory_id = await memory.store(
        context,
        request.content,
        layer=request.layer,
        importance=request.importance,
        tags=request.tags,
        metadata=request.metadata,
        session_id=request.session_id,
        scope=request.scope,
    )
    audit_store.record(action="memory.store", resource_type="memory", resource_id=memory_id, outcome="success", tenant_id=context.tenant_id, actor_id=context.user_id, details={"layer": request.layer, "importance": request.importance}, trace_id=context.trace_id)
    langfuse_client.log("memory.store", trace_id=context.trace_id, request_id=context.request_id, tenant_id=context.tenant_id, user_id=context.user_id, memory_id=memory_id, layer=request.layer)
    return MemoryStoreResponse(id=memory_id)


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(request: MemorySearchRequest, memory: MemoryDependency, principal: PrincipalDependency) -> MemorySearchResponse:
    enforce_scope(principal, "memory:read")
    context = _context_from_principal(principal)
    hits: list[MemorySearchHit] = []
    if hasattr(memory, "search_with_scores"):
        hits = await memory.search_with_scores(context, request.query, layers=request.layers, top_k=request.top_k, scope=request.scope)
    if hits:
        return MemorySearchResponse(items=[hit.item for hit in hits], hits=hits if request.include_scores else [])
    items = await memory.search(context, request.query, layers=request.layers, top_k=request.top_k, scope=request.scope)
    if not items and request.layers is not None and hasattr(memory, "layer_items"):
        query_terms = {term.lower() for term in request.query.split() if term.strip()}
        direct_items: list[MemoryItem] = []
        for layer in request.layers:
            for item in memory.layer_items(layer):
                content_terms = set(item.content.lower().split())
                if not query_terms or query_terms & content_terms:
                    direct_items.append(item)
        items = direct_items[: request.top_k]
    if request.include_scores and items:
        synthetic_hits = [
            MemorySearchHit(item=item, score=1.0, keyword_score=1.0, graph_score=0.0, vector_score=0.0, importance_score=item.importance, freshness_score=0.0)
            for item in items[: request.top_k]
        ]
        return MemorySearchResponse(items=items[: request.top_k], hits=synthetic_hits)
    return MemorySearchResponse(items=items[: request.top_k])


@router.post("/consolidate", response_model=MemoryConsolidationResult)
async def consolidate_memory(request: MemoryConsolidateRequest, memory: MemoryDependency, audit_store: AuditStoreDependency, principal: PrincipalDependency) -> MemoryConsolidationResult:
    enforce_scope(principal, "memory:write")
    context = _context_from_principal(principal)
    result = await memory.consolidate(context, source_layers=request.source_layers, target_layer=request.target_layer, max_items=request.max_items, min_importance=request.min_importance)
    audit_store.record(action="memory.consolidate", resource_type="memory", resource_id=result.target_memory_id, outcome="success" if result.target_memory_id else "skipped", tenant_id=context.tenant_id, actor_id=context.user_id, details={"source_count": result.source_count, "target_layer": request.target_layer}, trace_id=context.trace_id)
    langfuse_client.log("memory.consolidate", trace_id=context.trace_id, request_id=context.request_id, tenant_id=context.tenant_id, user_id=context.user_id, source_count=result.source_count, target_memory_id=result.target_memory_id)
    return result


@router.get("/layers")
async def memory_layers(memory: MemoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    layer_summary = memory.layer_summary() if hasattr(memory, "layer_summary") else []
    layer_roles = memory.layer_roles() if hasattr(memory, "layer_roles") else {}
    return {"layers": layer_summary, "layer_roles": layer_roles}


@router.get("/layers/{layer}")
async def memory_layer_detail(layer: int, memory: MemoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    if not hasattr(memory, "layer_profile") or not hasattr(memory, "layer_items"):
        return {"layer": layer, "items": [], "count": 0}
    profile = memory.layer_profile(layer)
    items = memory.layer_items(layer)
    return {"layer": layer, "profile": profile, "count": len(items), "items": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in items]}


@router.get("/sessions/{session_id}")
async def memory_session_detail(session_id: str, memory: MemoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    if not hasattr(memory, "session_summary"):
        return {"session_id": session_id, "summary": None, "items": [], "layers": []}
    summary = memory.session_summary(session_id)
    if summary is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Session not found.", trace_id=session_id)
    items = memory.session_items(session_id) if hasattr(memory, "session_items") else []
    layers = memory.session_memory_layers(session_id) if hasattr(memory, "session_memory_layers") else []
    return {"session_id": session_id, "summary": summary, "items": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in items], "layers": layers}


@router.get("/count")
async def memory_count(memory: MemoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    snapshot = memory.snapshot() if hasattr(memory, "snapshot") else {}
    count = snapshot.get("count", memory.count())
    layers = snapshot.get("layers", memory.layer_summary() if hasattr(memory, "layer_summary") else [])
    session_count = snapshot.get("session_count", memory.session_count() if hasattr(memory, "session_count") else 0)
    if hasattr(count, "__await__"):
        count = await count
    return {"count": int(count), "session_count": int(session_count), "layers": layers}


@router.get("/export", response_model=MemoryExportResponse)
async def export_memory(memory: MemoryDependency, principal: PrincipalDependency) -> MemoryExportResponse:
    enforce_scope(principal, "memory:read")
    bundle = memory.export_bundle(tenant_id=principal.tenant_id) if hasattr(memory, "export_bundle") else MemoryExportBundle()
    return MemoryExportResponse(bundle=bundle)


@router.post("/import", response_model=MemoryImportResponse)
async def import_memory(request: MemoryExportBundle, memory: MemoryDependency, principal: PrincipalDependency) -> MemoryImportResponse:
    enforce_scope(principal, "memory:write")
    if hasattr(memory, "import_bundle"):
        for item in request.memories:
            item.tenant_id = principal.tenant_id
        for session in request.sessions:
            session.tenant_id = principal.tenant_id
        result = memory.import_bundle(request)
    else:
        result = {"memories": 0, "sessions": 0}
    return MemoryImportResponse(memories=result.get("memories", 0), sessions=result.get("sessions", 0))


@router.get("/{memory_id}", response_model=MemoryItem)
async def get_memory_item(memory_id: str, memory: MemoryDependency, principal: PrincipalDependency) -> MemoryItem:
    enforce_scope(principal, "memory:read")
    if not hasattr(memory, "get_item"):
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Memory item not found.", trace_id=memory_id)
    item = memory.get_item(memory_id)
    if item is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Memory item not found.", trace_id=memory_id)
    if item.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Memory item not found.", trace_id=memory_id)
    return item


@router.get("/{memory_id}/correlation", response_model=dict[str, object])
async def get_memory_correlation(memory_id: str, memory: MemoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    if not hasattr(memory, "get_item"):
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Memory item not found.", trace_id=memory_id)
    item = memory.get_item(memory_id)
    if item is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Memory item not found.", trace_id=memory_id)
    if item.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Memory item not found.", trace_id=memory_id)
    trace_id = item.metadata.get("trace_id") or item.metadata.get("request_id") or item.id
    snapshot = {"resource_type": "memory_item", "resource_id": item.id, "trace_id": trace_id, "memory_id": item.id, "layer": item.layer, "tenant_id": item.tenant_id, "agent_id": item.agent_id, "session_id": item.session_id, "scope": item.scope.model_dump(mode="json"), "tags": item.tags}
    return {"memory_id": item.id, "trace_id": trace_id, "resource_type": "memory_item", "resource_id": item.id, "layer": item.layer, "tenant_id": item.tenant_id, "agent_id": item.agent_id, "session_id": item.session_id, "scope": item.scope.model_dump(mode="json"), "trace_summary": {"trace_id": trace_id, "event_count": 1, "started_at": item.created_at, "ended_at": item.created_at, "last_event": "memory.store", "task": item.metadata.get("memory_role", "memory"), "snapshot": snapshot}, "snapshot": snapshot}


def _context_from_principal(principal: Principal) -> RunContext:
    return RunContext(tenant_id=principal.tenant_id, user_id=principal.user_id, agent_id=principal.agent_id, request_id=principal.request_id, trace_id=principal.trace_id, permission_scope=principal.permission_scope)
