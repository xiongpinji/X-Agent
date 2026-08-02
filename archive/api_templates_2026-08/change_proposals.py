"""Change Proposals API — Codex-style batch file change workflow.

Allows the agent (or user) to propose a set of file changes as a single
changeset. Each proposal stores per-file diffs, supports review/approve/reject,
and applies changes atomically upon approval.

Endpoints:
    POST   /api/v1/change-proposals           — Create a change proposal
    GET    /api/v1/change-proposals           — List proposals
    GET    /api/v1/change-proposals/{id}      — Get proposal detail (with diffs)
    POST   /api/v1/change-proposals/{id}/approve — Approve & apply changes
    POST   /api/v1/change-proposals/{id}/reject  — Reject proposal
    DELETE /api/v1/change-proposals/{id}      — Delete proposal
"""

from __future__ import annotations

import difflib
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/change-proposals", tags=["change-proposals"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── Models ────────────────────────────────────────────────────────────────────


class FileChange(BaseModel):
    path: str = Field(..., description="Relative file path")
    action: str = Field(default="modify", description="create | modify | delete")
    new_content: str | None = Field(default=None, description="Full new content (for create/modify)")
    old_content: str | None = Field(default=None, description="Original content (auto-read if omitted)")


class ProposalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(default="")
    changes: list[FileChange] = Field(..., min_length=1)
    branch: str | None = Field(default=None, description="Target branch (informational)")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProposalRecord(BaseModel):
    id: str
    title: str
    description: str
    status: str  # pending | approved | rejected | applied
    changes: list[dict[str, Any]]
    diffs: list[dict[str, Any]]
    branch: str | None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str
    created_by: str
    reviewed_by: str | None = None
    review_comment: str | None = None


# ─── In-memory store (file-backed for persistence) ────────────────────────────

_PROPOSALS: dict[str, ProposalRecord] = {}
_STORE_DIR = Path(os.environ.get("XAGENT_DATA_DIR", ".xagent_runtime/data")) / "change_proposals"


def _persist(proposal: ProposalRecord) -> None:
    try:
        _STORE_DIR.mkdir(parents=True, exist_ok=True)
        import json
        (_STORE_DIR / f"{proposal.id}.json").write_text(
            json.dumps(proposal.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _load_all() -> None:
    global _PROPOSALS
    if _PROPOSALS:
        return
    try:
        import json
        if _STORE_DIR.exists():
            for f in _STORE_DIR.glob("*.json"):
                data = json.loads(f.read_text(encoding="utf-8"))
                _PROPOSALS[data["id"]] = ProposalRecord(**data)
    except Exception:
        pass


def _compute_diff(path: str, old: str | None, new: str | None, action: str) -> str:
    """Generate unified diff for a file change."""
    if action == "create":
        old_lines: list[str] = []
        new_lines = (new or "").splitlines(keepends=True)
    elif action == "delete":
        old_lines = (old or "").splitlines(keepends=True)
        new_lines = []
    else:
        old_lines = (old or "").splitlines(keepends=True)
        new_lines = (new or "").splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")
    return "".join(diff)


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_proposal(body: ProposalCreate, principal: PrincipalDependency) -> dict[str, Any]:
    """Create a new change proposal with computed diffs."""
    enforce_scope(principal, "agent:run")
    _load_all()

    workspace = os.environ.get("XAGENT_WORKSPACE", ".")
    diffs: list[dict[str, Any]] = []
    enriched_changes: list[dict[str, Any]] = []

    for change in body.changes:
        file_path = Path(workspace) / change.path
        old_content = change.old_content
        if old_content is None and change.action != "create" and file_path.exists():
            try:
                old_content = file_path.read_text(encoding="utf-8")
            except Exception:
                old_content = ""

        diff_text = _compute_diff(change.path, old_content, change.new_content, change.action)
        diffs.append({
            "path": change.path,
            "action": change.action,
            "diff": diff_text,
            "additions": diff_text.count("\n+") - diff_text.count("\n+++"),
            "deletions": diff_text.count("\n-") - diff_text.count("\n---"),
        })
        enriched_changes.append({
            "path": change.path,
            "action": change.action,
            "new_content": change.new_content,
            "old_content": old_content,
        })

    now = datetime.now(UTC).isoformat()
    proposal = ProposalRecord(
        id=str(uuid4()),
        title=body.title,
        description=body.description,
        status="pending",
        changes=enriched_changes,
        diffs=diffs,
        branch=body.branch,
        metadata=body.metadata,
        created_at=now,
        updated_at=now,
        created_by=principal.user_id,
    )
    _PROPOSALS[proposal.id] = proposal
    _persist(proposal)

    return {
        "id": proposal.id,
        "title": proposal.title,
        "status": proposal.status,
        "file_count": len(diffs),
        "total_additions": sum(d["additions"] for d in diffs),
        "total_deletions": sum(d["deletions"] for d in diffs),
        "diffs": diffs,
        "created_at": now,
    }


@router.get("")
async def list_proposals(principal: PrincipalDependency, status: str | None = None) -> dict[str, Any]:
    """List all change proposals, optionally filtered by status."""
    enforce_scope(principal, "agent:run")
    _load_all()
    items = list(_PROPOSALS.values())
    if status:
        items = [p for p in items if p.status == status]
    items.sort(key=lambda p: p.created_at, reverse=True)
    return {
        "proposals": [
            {
                "id": p.id,
                "title": p.title,
                "status": p.status,
                "file_count": len(p.changes),
                "created_at": p.created_at,
                "created_by": p.created_by,
            }
            for p in items[:50]
        ],
        "total": len(items),
    }


@router.get("/{proposal_id}")
async def get_proposal(proposal_id: str, principal: PrincipalDependency) -> dict[str, Any]:
    """Get full proposal detail including diffs."""
    enforce_scope(principal, "agent:run")
    _load_all()
    proposal = _PROPOSALS.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal.model_dump()


@router.post("/{proposal_id}/approve")
async def approve_proposal(proposal_id: str, principal: PrincipalDependency, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Approve and apply all file changes atomically."""
    enforce_scope(principal, "agent:run")
    _load_all()
    proposal = _PROPOSALS.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail=f"Proposal already {proposal.status}")

    workspace = os.environ.get("XAGENT_WORKSPACE", ".")
    applied: list[str] = []
    errors: list[str] = []

    for change in proposal.changes:
        file_path = Path(workspace) / change["path"]
        try:
            if change["action"] == "delete":
                if file_path.exists():
                    file_path.unlink()
                applied.append(f"deleted: {change['path']}")
            else:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(change.get("new_content") or "", encoding="utf-8")
                applied.append(f"{'created' if change['action'] == 'create' else 'modified'}: {change['path']}")
        except Exception as exc:
            errors.append(f"{change['path']}: {exc}")

    now = datetime.now(UTC).isoformat()
    proposal.status = "applied" if not errors else "approved"
    proposal.updated_at = now
    proposal.reviewed_by = principal.user_id
    proposal.review_comment = (body or {}).get("comment", "")
    _persist(proposal)

    return {
        "id": proposal.id,
        "status": proposal.status,
        "applied": applied,
        "errors": errors,
        "reviewed_by": principal.user_id,
    }


@router.post("/{proposal_id}/reject")
async def reject_proposal(proposal_id: str, principal: PrincipalDependency, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reject a change proposal."""
    enforce_scope(principal, "agent:run")
    _load_all()
    proposal = _PROPOSALS.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail=f"Proposal already {proposal.status}")

    proposal.status = "rejected"
    proposal.updated_at = datetime.now(UTC).isoformat()
    proposal.reviewed_by = principal.user_id
    proposal.review_comment = (body or {}).get("comment", "")
    _persist(proposal)

    return {"id": proposal.id, "status": "rejected", "reviewed_by": principal.user_id}


@router.delete("/{proposal_id}", status_code=204)
async def delete_proposal(proposal_id: str, principal: PrincipalDependency) -> None:
    """Delete a change proposal."""
    enforce_scope(principal, "agent:run")
    _load_all()
    if proposal_id not in _PROPOSALS:
        raise HTTPException(status_code=404, detail="Proposal not found")
    del _PROPOSALS[proposal_id]
    try:
        (_STORE_DIR / f"{proposal_id}.json").unlink(missing_ok=True)
    except Exception:
        pass
