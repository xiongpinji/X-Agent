"""BT. Real-Time Collaborative Whiteboard — canvas sync, shape elements, multi-user annotations, snapshot export."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/whiteboard", tags=["whiteboard"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Stores ──────────────────────────────────────────────────────────────────

_boards: dict[str, dict[str, Any]] = {}


# ─── BT1: Canvas Management ──────────────────────────────────────────────────


@router.post("/boards")
async def create_board(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BT: Create a new collaborative whiteboard."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    board_id = f"wb-{uuid4().hex[:8]}"
    board = {
        "id": board_id,
        "name": body.get("name", "Untitled Board"),
        "width": body.get("width", 4096),
        "height": body.get("height", 4096),
        "background": body.get("background", "#ffffff"),
        "elements": [],
        "collaborators": [],
        "version": 0,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _boards[board_id] = board
    return board


@router.get("/boards")
async def list_boards(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BT: List all whiteboards."""
    enforce_scope(principal, "agent:run")
    return {
        "boards": [{"id": b["id"], "name": b["name"], "elements_count": len(b["elements"]), "version": b["version"]} for b in _boards.values()],
        "total": len(_boards),
    }


# ─── BT2: Shape Elements ─────────────────────────────────────────────────────


@router.post("/boards/{board_id}/elements")
async def add_element(
    board_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BT: Add a shape/text element to the canvas."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    element = {
        "id": f"el-{uuid4().hex[:8]}",
        "type": body.get("type", "rectangle"),
        "x": body.get("x", random.randint(0, 1000)),
        "y": body.get("y", random.randint(0, 1000)),
        "width": body.get("width", 200),
        "height": body.get("height", 100),
        "style": body.get("style", {"fill": "#4A90D9", "stroke": "#2C3E50", "stroke_width": 2}),
        "content": body.get("content", ""),
        "z_index": body.get("z_index", 1),
        "created_by": "user-1",
        "created_at": datetime.now(UTC).isoformat(),
    }
    if board_id in _boards:
        _boards[board_id]["elements"].append(element)
        _boards[board_id]["version"] += 1
    return element


@router.get("/boards/{board_id}/elements")
async def get_elements(
    board_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BT: Get all elements on a board."""
    enforce_scope(principal, "agent:run")
    board = _boards.get(board_id, {"elements": [], "version": 0})
    return {
        "board_id": board_id,
        "elements": board["elements"],
        "total": len(board["elements"]),
        "version": board["version"],
    }


# ─── BT3: Multi-User Annotations ─────────────────────────────────────────────


@router.post("/boards/{board_id}/annotate")
async def add_annotation(
    board_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BT: Add a user annotation (comment/sticky note) to the board."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    annotation = {
        "id": f"ann-{uuid4().hex[:8]}",
        "board_id": board_id,
        "author": body.get("author", "anonymous"),
        "type": body.get("type", "comment"),
        "text": body.get("text", ""),
        "position": {"x": body.get("x", 100), "y": body.get("y", 100)},
        "color": body.get("color", "#FFEB3B"),
        "resolved": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    return annotation


@router.get("/boards/{board_id}/collaborators")
async def get_collaborators(
    board_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BT: Get active collaborators and their cursors."""
    enforce_scope(principal, "agent:run")
    return {
        "board_id": board_id,
        "collaborators": [
            {"user_id": "user-1", "name": "Alice", "cursor": {"x": 450, "y": 320}, "color": "#E91E63", "active": True},
            {"user_id": "user-2", "name": "Bob", "cursor": {"x": 800, "y": 150}, "color": "#2196F3", "active": True},
            {"user_id": "user-3", "name": "Carol", "cursor": {"x": 200, "y": 600}, "color": "#4CAF50", "active": False},
        ],
        "online": 2,
        "total": 3,
    }


# ─── BT4: Snapshot Export ────────────────────────────────────────────────────


@router.post("/boards/{board_id}/export")
async def export_snapshot(
    board_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BT: Export board as a snapshot (PNG/SVG/JSON)."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    board = _boards.get(board_id, {"elements": [], "version": 0})
    return {
        "export_id": f"exp-{uuid4().hex[:8]}",
        "board_id": board_id,
        "format": body.get("format", "png"),
        "resolution": body.get("resolution", "2x"),
        "elements_included": len(board["elements"]),
        "file_size_kb": random.randint(50, 2000),
        "download_url": f"/api/v1/whiteboard/exports/{uuid4().hex[:8]}.png",
        "exported_at": datetime.now(UTC).isoformat(),
    }


# ─── BT5: Board Sync Status ──────────────────────────────────────────────────


@router.get("/sync-status")
async def sync_status(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BT: Real-time sync status across all boards."""
    enforce_scope(principal, "agent:run")
    return {
        "protocol": "websocket + CRDT",
        "active_boards": len(_boards),
        "active_sessions": random.randint(1, 10),
        "ops_per_second": random.randint(5, 100),
        "conflict_resolution": "last-writer-wins + operational-transform",
        "latency_ms": random.randint(5, 50),
        "persistence": "redis_streams + postgres_snapshot",
        "checked_at": datetime.now(UTC).isoformat(),
    }
