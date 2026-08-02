"""Advanced Memory API — episodic, procedural and cross-session memory.

Endpoints (all under the ``/api/v1/memory`` prefix; sub-paths are chosen to
avoid conflicts with the primary memory API in ``backend/app/api/memory.py``
and the enhanced API in ``backend/app/api/memory_enhanced.py``):

- GET  /api/v1/memory/episodes            - list / search episodes
- POST /api/v1/memory/episodes            - record a new episode
- POST /api/v1/memory/episodes/recall     - recall episodes by similarity
- POST /api/v1/memory/episodes/summarize  - compress old episodes
- GET  /api/v1/memory/procedures          - list procedures
- POST /api/v1/memory/procedures          - store a procedure
- POST /api/v1/memory/procedures/match    - match current context (fast-path)
- GET  /api/v1/memory/preferences         - user preferences
- POST /api/v1/memory/preferences/extract - extract preference from correction
- POST /api/v1/memory/knowledge/query     - query knowledge graph
- GET  /api/v1/memory/advanced/stats      - aggregate statistics
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.app.core.memory_cross_session import cross_session_memory
from backend.app.core.memory_episodic import episodic_memory_store
from backend.app.core.memory_procedural import procedural_memory
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/memory", tags=["memory-advanced"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ---------------------------------------------------------------------------
# Episodic models
# ---------------------------------------------------------------------------


class EpisodeOut(BaseModel):
    id: str
    session_id: str = ""
    timestamp: str
    actor: str = "agent"
    action: str = ""
    target: str = ""
    outcome: str = ""
    importance: int = 5
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    context: str = ""
    emotion: str = ""
    is_summary: bool = False


class EpisodeRecordRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=20_000)
    session_id: str = ""
    actor: str = "agent"
    target: str = ""
    outcome: str = ""
    importance: int = Field(default=5, ge=1, le=10)
    tags: list[str] = Field(default_factory=list)
    context: str = ""
    emotion: str = ""
    summary: str = ""


class EpisodeRecallRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    session_id: str | None = None


class EpisodeRecallHit(BaseModel):
    episode: EpisodeOut
    score: float


class EpisodeSummarizeRequest(BaseModel):
    older_than_days: int = Field(default=7, ge=1, le=3650)
    period_label: str = ""
    min_batch: int = Field(default=5, ge=1, le=1000)
    delete_originals: bool = False


def _episode_to_out(ep: Any) -> EpisodeOut:
    return EpisodeOut(
        id=ep.id,
        session_id=ep.session_id,
        timestamp=ep.timestamp.isoformat(),
        actor=ep.actor,
        action=ep.action,
        target=ep.target,
        outcome=ep.outcome,
        importance=ep.importance,
        tags=ep.tags,
        summary=ep.summary,
        context=ep.context,
        emotion=ep.emotion,
        is_summary=ep.is_summary,
    )


@router.get("/episodes", response_model=list[EpisodeOut])
async def list_episodes(
    principal: PrincipalDependency,
    q: str | None = Query(default=None, description="Full-text search query"),
    session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    min_importance: int | None = Query(default=None, ge=1, le=10),
    tags: str | None = Query(default=None, description="Comma-separated tags"),
) -> list[EpisodeOut]:
    """List or search episodes (FTS5 search when ``q`` is provided)."""
    if q:
        episodes = await episodic_memory_store.search_episodes(
            q, limit=limit, session_id=session_id
        )
    elif min_importance is not None:
        episodes = await episodic_memory_store.recall_by_importance(
            min_importance, limit=limit, session_id=session_id
        )
    elif tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        episodes = await episodic_memory_store.recall_by_tags(tag_list, limit=limit)
    else:
        episodes = await episodic_memory_store.list_episodes(
            limit=limit, session_id=session_id
        )
    return [_episode_to_out(ep) for ep in episodes]


@router.post("/episodes", response_model=EpisodeOut)
async def record_episode(request: EpisodeRecordRequest, principal: PrincipalDependency) -> EpisodeOut:
    """Record a new episode."""
    ep = await episodic_memory_store.record_episode(
        action=request.action,
        session_id=request.session_id,
        actor=request.actor,
        target=request.target,
        outcome=request.outcome,
        importance=request.importance,
        tags=request.tags,
        context=request.context,
        emotion=request.emotion,
        summary=request.summary,
    )
    return _episode_to_out(ep)


@router.post("/episodes/recall", response_model=list[EpisodeRecallHit])
async def recall_episodes(
    request: EpisodeRecallRequest, principal: PrincipalDependency
) -> list[EpisodeRecallHit]:
    """Recall episodes by similarity to a query."""
    hits = await episodic_memory_store.recall_by_similarity(
        request.query, limit=request.limit, session_id=request.session_id
    )
    return [EpisodeRecallHit(episode=_episode_to_out(ep), score=score) for ep, score in hits]


@router.post("/episodes/summarize")
async def summarize_episodes(
    request: EpisodeSummarizeRequest, principal: PrincipalDependency
) -> dict[str, Any]:
    """Compress old episodes into a summary episode."""
    summary_ep = await episodic_memory_store.summarize_old_episodes(
        older_than_days=request.older_than_days,
        period_label=request.period_label,
        min_batch=request.min_batch,
        delete_originals=request.delete_originals,
    )
    if summary_ep is None:
        return {"summarized": False, "reason": "not enough episodes to summarize"}
    return {
        "summarized": True,
        "summary_id": summary_ep.id,
        "episode_count": len(summary_ep.summarized_episode_ids),
        "summary": summary_ep.summary,
    }


# ---------------------------------------------------------------------------
# Procedural models
# ---------------------------------------------------------------------------


class ProcedureOut(BaseModel):
    id: str
    name: str
    trigger_pattern: str
    steps: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    success_count: int = 0
    failure_count: int = 0
    reliability: float = 0.0
    last_used: str | None = None
    avg_time_saved: float = 0.0
    tags: list[str] = Field(default_factory=list)


class ProcedureStoreRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    trigger_pattern: str = Field(..., min_length=1, max_length=5000)
    steps: list[str] = Field(..., min_length=1)
    expected_outcome: str = ""
    tags: list[str] = Field(default_factory=list)


class ProcedureMatchRequest(BaseModel):
    context: str = Field(..., min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=50)
    threshold: float = Field(default=0.15, ge=0.0, le=1.0)


class ProcedureMatchOut(BaseModel):
    procedure: ProcedureOut
    score: float
    matched_terms: list[str] = Field(default_factory=list)


def _procedure_to_out(proc: Any) -> ProcedureOut:
    return ProcedureOut(
        id=proc.id,
        name=proc.name,
        trigger_pattern=proc.trigger_pattern,
        steps=proc.steps,
        expected_outcome=proc.expected_outcome,
        success_count=proc.success_count,
        failure_count=proc.failure_count,
        reliability=round(proc.reliability, 4),
        last_used=proc.last_used.isoformat() if proc.last_used else None,
        avg_time_saved=proc.avg_time_saved,
        tags=proc.tags,
    )


@router.get("/procedures", response_model=list[ProcedureOut])
async def list_procedures(
    principal: PrincipalDependency,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ProcedureOut]:
    """List stored procedures (ranked by success count / reliability)."""
    procs = await procedural_memory.list_procedures(limit=limit)
    return [_procedure_to_out(p) for p in procs]


@router.post("/procedures", response_model=ProcedureOut)
async def store_procedure(
    request: ProcedureStoreRequest, principal: PrincipalDependency
) -> ProcedureOut:
    """Explicitly store a procedure."""
    proc = await procedural_memory.store_procedure(
        name=request.name,
        trigger_pattern=request.trigger_pattern,
        steps=request.steps,
        expected_outcome=request.expected_outcome,
        tags=request.tags,
    )
    return _procedure_to_out(proc)


@router.post("/procedures/match", response_model=list[ProcedureMatchOut])
async def match_procedures(
    request: ProcedureMatchRequest, principal: PrincipalDependency
) -> list[ProcedureMatchOut]:
    """Match the current task context against stored procedures (fast-path)."""
    matches = await procedural_memory.match_context(
        request.context, top_k=request.top_k, threshold=request.threshold
    )
    return [
        ProcedureMatchOut(
            procedure=_procedure_to_out(m.procedure),
            score=round(m.score, 4),
            matched_terms=m.matched_terms,
        )
        for m in matches
    ]


# ---------------------------------------------------------------------------
# Cross-session models (preferences + knowledge graph)
# ---------------------------------------------------------------------------


class PreferenceOut(BaseModel):
    key: str
    value: str
    confidence: float
    source_session: str = ""
    created_at: str
    last_confirmed: str
    confirmation_count: int = 1


class PreferenceSetRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=500)
    value: str = Field(..., min_length=1, max_length=5000)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class PreferenceExtractRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10_000)
    source_session: str = ""


class KnowledgeQueryRequest(BaseModel):
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class KnowledgeTripleRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    predicate: str = Field(..., min_length=1, max_length=500)
    object: str = Field(..., min_length=1, max_length=500)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


def _preference_to_out(pref: Any) -> PreferenceOut:
    return PreferenceOut(
        key=pref.key,
        value=pref.value,
        confidence=pref.confidence,
        source_session=pref.source_session,
        created_at=pref.created_at.isoformat(),
        last_confirmed=pref.last_confirmed.isoformat(),
        confirmation_count=pref.confirmation_count,
    )


@router.get("/preferences", response_model=list[PreferenceOut])
async def list_preferences(
    principal: PrincipalDependency,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[PreferenceOut]:
    """List persisted user preferences."""
    prefs = await cross_session_memory.list_preferences(limit=limit)
    return [_preference_to_out(p) for p in prefs]


@router.post("/preferences", response_model=PreferenceOut)
async def set_preference(
    request: PreferenceSetRequest, principal: PrincipalDependency
) -> PreferenceOut:
    """Set or update a user preference (newer overrides older)."""
    pref = await cross_session_memory.set_preference(
        key=request.key, value=request.value, confidence=request.confidence
    )
    return _preference_to_out(pref)


@router.post("/preferences/extract")
async def extract_preference(
    request: PreferenceExtractRequest, principal: PrincipalDependency
) -> dict[str, Any]:
    """Auto-extract a preference from a user correction."""
    pref = await cross_session_memory.extract_preference_from_correction(
        request.text, source_session=request.source_session
    )
    if pref is None:
        return {"extracted": False, "reason": "no correction pattern detected"}
    return {"extracted": True, "preference": _preference_to_out(pref).model_dump()}


@router.post("/knowledge/query")
async def query_knowledge(
    request: KnowledgeQueryRequest, principal: PrincipalDependency
) -> dict[str, Any]:
    """Query the knowledge graph by subject/predicate/object."""
    triples = await cross_session_memory.query_triples(
        subject=request.subject,
        predicate=request.predicate,
        obj=request.object,
        limit=request.limit,
    )
    return {
        "count": len(triples),
        "triples": [t.to_dict() for t in triples],
    }


@router.post("/knowledge", status_code=201)
async def add_knowledge(
    request: KnowledgeTripleRequest, principal: PrincipalDependency
) -> dict[str, Any]:
    """Add or update a knowledge-graph triple."""
    triple = await cross_session_memory.add_triple(
        subject=request.subject,
        predicate=request.predicate,
        obj=request.object,
        confidence=request.confidence,
        evidence=request.evidence,
    )
    return triple.to_dict()


# ---------------------------------------------------------------------------
# Aggregate stats
# ---------------------------------------------------------------------------


@router.get("/advanced/stats")
async def advanced_memory_stats(principal: PrincipalDependency) -> dict[str, Any]:
    """Aggregate statistics across the three advanced memory layers."""
    episodic = await episodic_memory_store.get_stats()
    procedural = await procedural_memory.get_stats()
    cross_session = await cross_session_memory.get_stats()
    return {
        "episodic": episodic,
        "procedural": procedural,
        "cross_session": cross_session,
    }
