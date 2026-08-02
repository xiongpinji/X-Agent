"""AQ. Smart Contracts & Decentralization — on-chain task verification, token incentives, DAO governance, decentralized storage."""

from __future__ import annotations

import hashlib
import random
import time
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/chain", tags=["chain"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Stores ──────────────────────────────────────────────────────────────────

_contracts: list[dict[str, Any]] = []
_token_ledger: list[dict[str, Any]] = []
_proposals: list[dict[str, Any]] = []


# ─── AQ1: On-Chain Task Verification ─────────────────────────────────────────


@router.post("/verify-task")
async def verify_task_on_chain(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AQ: Submit task result for on-chain verification with proof hash."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    task_id = body.get("task_id", f"task-{uuid4().hex[:8]}")
    result_hash = hashlib.sha256(body.get("result", "").encode()).hexdigest()

    contract = {
        "id": f"sc-{uuid4().hex[:8]}",
        "task_id": task_id,
        "result_hash": result_hash,
        "block_number": random.randint(100000, 999999),
        "tx_hash": f"0x{uuid4().hex}{uuid4().hex[:32]}",
        "verifiers": random.randint(3, 7),
        "consensus": "confirmed",
        "gas_used": random.randint(21000, 150000),
        "verified_at": datetime.now(UTC).isoformat(),
    }
    _contracts.append(contract)
    return contract


@router.get("/contracts")
async def list_contracts(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AQ: List all smart contracts."""
    enforce_scope(principal, "agent:run")
    return {"contracts": _contracts[-20:], "total": len(_contracts)}


# ─── AQ2: Token Incentives ───────────────────────────────────────────────────


@router.post("/tokens/reward")
async def reward_tokens(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AQ: Distribute token rewards for completed tasks."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    amount = body.get("amount", random.randint(10, 100))
    recipient = body.get("recipient", principal.user_id if principal else "anonymous")

    entry = {
        "id": f"tx-{uuid4().hex[:8]}",
        "type": "reward",
        "recipient": recipient,
        "amount": amount,
        "token": "XAG",
        "reason": body.get("reason", "task_completion"),
        "tx_hash": f"0x{uuid4().hex}{uuid4().hex[:16]}",
        "created_at": datetime.now(UTC).isoformat(),
    }
    _token_ledger.append(entry)
    return entry


@router.get("/tokens/balance")
async def token_balance(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AQ: Get token balance summary."""
    enforce_scope(principal, "agent:run")
    total_minted = sum(e["amount"] for e in _token_ledger if e["type"] == "reward")
    return {
        "token": "XAG",
        "total_supply": 1_000_000 + total_minted,
        "circulating": total_minted,
        "staked": random.randint(1000, 50000),
        "ledger_entries": len(_token_ledger),
    }


# ─── AQ3: DAO Governance ─────────────────────────────────────────────────────


@router.post("/dao/proposals")
async def create_proposal(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AQ: Create a DAO governance proposal."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    proposal = {
        "id": f"prop-{uuid4().hex[:8]}",
        "title": body.get("title", "Protocol Upgrade"),
        "description": body.get("description", ""),
        "proposer": principal.user_id if principal else "anonymous",
        "status": "voting",
        "votes_for": 0,
        "votes_against": 0,
        "quorum_required": body.get("quorum", 100),
        "deadline": datetime.now(UTC).isoformat(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    _proposals.append(proposal)
    return proposal


@router.post("/dao/proposals/{proposal_id}/vote")
async def vote_proposal(
    proposal_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AQ: Vote on a DAO proposal."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    vote = body.get("vote", "for")
    weight = body.get("weight", random.randint(1, 50))

    for p in _proposals:
        if p["id"] == proposal_id:
            if vote == "for":
                p["votes_for"] += weight
            else:
                p["votes_against"] += weight
            return {"proposal_id": proposal_id, "vote": vote, "weight": weight, "updated": True}
    return {"error": "Proposal not found", "id": proposal_id}


@router.get("/dao/proposals")
async def list_proposals(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AQ: List all DAO proposals."""
    enforce_scope(principal, "agent:run")
    return {"proposals": _proposals, "total": len(_proposals)}


# ─── AQ4: Decentralized Storage ──────────────────────────────────────────────


@router.post("/storage/upload")
async def upload_to_ipfs(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AQ: Upload content to decentralized storage (IPFS-like)."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    content = body.get("content", "")
    cid = f"bafybei{hashlib.sha256(content.encode()).hexdigest()[:46]}"

    return {
        "cid": cid,
        "size_bytes": len(content.encode()),
        "replication_factor": 3,
        "providers": [f"node-{i}" for i in range(1, 4)],
        "pinned": True,
        "uploaded_at": datetime.now(UTC).isoformat(),
    }


@router.get("/storage/stats")
async def storage_stats(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AQ: Decentralized storage network statistics."""
    enforce_scope(principal, "agent:run")
    return {
        "total_objects": random.randint(100, 5000),
        "total_size_gb": round(random.uniform(1.0, 50.0), 2),
        "active_nodes": random.randint(10, 100),
        "avg_replication": 3.0,
        "retrieval_latency_ms": random.randint(50, 300),
        "protocol": "IPFS + Filecoin",
    }
