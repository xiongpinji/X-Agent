from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode, RunContext
from backend.app.core.memory import MemoryConsolidationResult
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal, get_memory

router = APIRouter(prefix="/api/v1/migration", tags=["migration"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class ExternalMemoryItem(BaseModel):
    content: str = Field(..., min_length=1, max_length=20_000)
    layer: int = Field(default=3, ge=1, le=4)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class ExternalMemoryImportRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=80)
    source_app: str = Field(..., min_length=1, max_length=80)
    tenant_id: str = "default"
    user_id: str = "anonymous"
    memories: list[ExternalMemoryItem] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class ExternalMemoryImportResponse(BaseModel):
    imported_count: int
    target_count: int
    imported_ids: list[str] = Field(default_factory=list)
    source: str
    source_app: str
    snapshot: dict[str, object] = Field(default_factory=dict)


@router.post("/memories/import", response_model=ExternalMemoryImportResponse)
async def import_memories(
    request: ExternalMemoryImportRequest,
    principal: PrincipalDependency,
) -> ExternalMemoryImportResponse:
    enforce_scope(principal, "memory:write")
    memory = get_memory()
    if not hasattr(memory, "store"):
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Current memory backend does not support import.")

    context = RunContext(
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        request_id=f"migration-{request.source_app}",
    )
    imported_ids: list[str] = []
    for item in request.memories:
        memory_id = await memory.store(
            context,
            item.content,
            layer=item.layer,
            importance=item.importance,
            tags=[request.source_app, request.source, *item.tags],
            metadata={
                **item.metadata,
                **request.metadata,
                "source": request.source,
                "source_app": request.source_app,
                "imported_from": request.source_app,
            },
        )
        imported_ids.append(memory_id)

    target_count = memory.count() if hasattr(memory, "count") else len(imported_ids)
    return ExternalMemoryImportResponse(
        imported_count=len(imported_ids),
        target_count=target_count,
        imported_ids=imported_ids,
        source=request.source,
        source_app=request.source_app,
        snapshot={
            "source": request.source,
            "source_app": request.source_app,
            "imported_count": len(imported_ids),
            "target_count": target_count,
        },
    )
