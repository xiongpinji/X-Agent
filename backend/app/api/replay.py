from __future__ import annotations

import dataclasses

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.linked_summary import build_linked_summary
from backend.app.core.code_index import code_index
from backend.app.core.execution_planner import execution_planner
from backend.app.core.memory import MemorySystem
from backend.app.core.replay import replay_engine
from backend.app.core.security import Principal
from backend.app.core.test_mapper import test_mapper
from backend.app.core.verification import VerificationEngine
from backend.app.dependencies import enforce_scope, get_audit_store, get_current_principal, get_memory

router = APIRouter(prefix="/api/v1/replay", tags=["replay"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

_verification_engine = VerificationEngine()


@router.post("/draft")
async def draft_replay(payload: dict[str, object], principal: PrincipalDependency, memory: Annotated[MemorySystem, Depends(get_memory)], audit_store: Annotated[object, Depends(get_audit_store)]) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    task = str(payload.get("task", ""))
    root = str(payload.get("root", "."))
    trace_id = str(payload.get("trace_id", ""))
    session_id = str(payload.get("session_id", ""))
    indexed = code_index.index(root=root, limit=int(payload.get("limit", 500)))
    mapping = test_mapper.map(task, limit=int(payload.get("limit", 10)))
    plan = execution_planner.build(task, test_mapping=mapping)
    verification = _verification_engine.summarize_run([], test_mapping=mapping)
    replay_view = replay_engine.build_continuous(trace_id) if trace_id else {}
    memory_summary = memory.session_summary(session_id) if session_id and hasattr(memory, "session_summary") else None
    memory_layers = memory.session_memory_layers(session_id) if session_id and hasattr(memory, "session_memory_layers") else []
    memory_items = memory.session_items(session_id) if session_id and hasattr(memory, "session_items") else []
    audit_records = audit_store.list(limit=20, tenant_id=principal.tenant_id, action="memory.store") if hasattr(audit_store, "list") else []
    audit_chain = [record.model_dump(mode="json") if hasattr(record, "model_dump") else record for record in audit_records if (not trace_id or str(getattr(record, "trace_id", "")) == trace_id) or (not session_id or str(getattr(record, "details", {}).get("session_id", "")) == session_id)]
    audit_verification = audit_store.verify_chain().model_dump(mode="json") if hasattr(audit_store, "verify_chain") else {}
    primary = {
        "task": task,
        "trace_id": trace_id,
        "session_id": session_id,
        "code_index": {
            "related_files": code_index.related_files(task, limit=10),
            "impact_hints": code_index.impact_hints(task, limit=10),
            "test_files": code_index.test_files_for(task, limit=10),
        },
        "execution_plan": dataclasses.asdict(plan),
        "verification": verification,
        "replay": replay_view,
        "audit": {
            "count": len(audit_chain),
            "latest": audit_chain[:1],
            "chain_preview": audit_chain[:5],
            "verification": audit_verification,
        },
        "memory": {
            "summary": memory_summary,
            "layers": [layer if isinstance(layer, dict) else layer for layer in memory_layers],
            "items": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in memory_items],
        },
    }
    return build_linked_summary(
        resource_type="replay_draft",
        resource_id=trace_id or session_id or task,
        primary=primary,
        trace={"data": {"verification": verification, "replay": replay_view}, "summary": {"trace_id": trace_id, "task": task}},
        audit={"data": {"audit": primary["audit"]}, "summary": {"count": len(audit_chain), "verified": bool(audit_verification)}},
        memory={"data": {"memory": primary["memory"]}, "summary": {"has_summary": memory_summary is not None, "layer_count": len(memory_layers)}},
        workflow={"data": {"execution_plan": primary["execution_plan"]}, "summary": {"task": task, "test_files": len(primary["code_index"]["test_files"])}},
        extra={"summary": {"trace_id": trace_id, "session_id": session_id, "code_index_count": indexed["count"]}, "code_index": primary["code_index"]},
    )
