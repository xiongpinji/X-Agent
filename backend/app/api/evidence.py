"""证据驱动完成 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.core.evidence.storage import EvidenceStorage
from backend.app.core.evidence.verifier import EvidenceVerifier

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])

_storage = EvidenceStorage()
_verifier = EvidenceVerifier()


@router.get("/{run_id}")
async def get_evidence(run_id: str) -> dict[str, Any]:
    """获取指定运行的完整证据包。"""
    evidence = _storage.load(run_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail=f"未找到 run_id={run_id} 的证据")
    return evidence.to_dict()


@router.post("/{run_id}/verify")
async def verify_evidence(run_id: str) -> dict[str, Any]:
    """手动触发证据验证。"""
    evidence = _storage.load(run_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail=f"未找到 run_id={run_id} 的证据")
    passed, notes = _verifier.verify(evidence)
    _storage.save(evidence)
    return {"run_id": run_id, "verification_passed": passed, "notes": notes}


@router.get("")
async def list_evidence() -> dict[str, Any]:
    """列出所有已存储的证据 run_id。"""
    return {"run_ids": _storage.list_all()}
