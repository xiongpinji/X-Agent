"""P2-03: GDPR 数据主体权利 API.

端点:
- POST /api/v1/gdpr/erase — 删除权 (Art. 17)
- POST /api/v1/gdpr/export — 导出权 (Art. 20)
- GET  /api/v1/gdpr/deletions — 删除请求记录
- GET  /api/v1/gdpr/deletions/{request_id} — 删除证明
- POST /api/v1/gdpr/pii/scan — PII 扫描
- POST /api/v1/gdpr/pii/mask — PII 脱敏
- GET  /api/v1/gdpr/residency — 数据驻留配置
- PUT  /api/v1/gdpr/residency/{tenant_id} — 设置驻留规则
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.gdpr.pii import MaskStrategy, PIIDetector, PIIMasker
from backend.app.core.gdpr.residency import DataRegion, get_residency_config
from backend.app.core.gdpr.service import DataSubjectRightsService

router = APIRouter(prefix="/api/v1/gdpr", tags=["gdpr"])

_service = DataSubjectRightsService()
_detector = PIIDetector()
_masker = PIIMasker()


# ─── 请求/响应模型 ────────────────────────────────────────────────────────────


class EraseRequest(BaseModel):
    user_id: str
    tenant_id: str = ""


class EraseResponse(BaseModel):
    request_id: str
    user_id: str
    deleted_counts: dict[str, int]
    total_deleted: int
    errors: list[str]
    success: bool
    completed_at: str


class ExportRequest(BaseModel):
    user_id: str
    tenant_id: str = ""


class ExportResponse(BaseModel):
    request_id: str
    user_id: str
    record_counts: dict[str, int]
    total_records: int
    data: dict
    exported_at: str


class PIIScanRequest(BaseModel):
    text: str


class PIIScanResponse(BaseModel):
    has_pii: bool
    pii_count: int
    matches: list[dict]


class PIIMaskRequest(BaseModel):
    text: str
    strategy: str = "mask"  # mask | hash | remove | generalize


class PIIMaskResponse(BaseModel):
    original_length: int
    masked_text: str
    pii_count: int


class ResidencyRuleRequest(BaseModel):
    region: str
    allowed_regions: list[str] = Field(default_factory=list)
    block_cross_border: bool = True


class ResidencyRuleResponse(BaseModel):
    tenant_id: str
    region: str
    allowed_regions: list[str]
    block_cross_border: bool


# ─── 删除权 ───────────────────────────────────────────────────────────────────


@router.post("/erase", response_model=EraseResponse)
def erase_user_data(req: EraseRequest):
    """GDPR Art.17: 删除用户所有数据."""
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    result = _service.erase_user_data(req.user_id, req.tenant_id)
    return EraseResponse(
        request_id=result.request_id,
        user_id=result.user_id,
        deleted_counts=result.deleted_counts,
        total_deleted=result.total_deleted,
        errors=result.errors,
        success=result.success,
        completed_at=result.completed_at,
    )


# ─── 导出权 ───────────────────────────────────────────────────────────────────


@router.post("/export", response_model=ExportResponse)
def export_user_data(req: ExportRequest):
    """GDPR Art.20: 导出用户所有数据."""
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    result = _service.export_user_data(req.user_id, req.tenant_id)
    return ExportResponse(
        request_id=result.request_id,
        user_id=result.user_id,
        record_counts=result.record_counts,
        total_records=result.total_records,
        data=result.data,
        exported_at=result.exported_at,
    )


# ─── 删除记录 ─────────────────────────────────────────────────────────────────


@router.get("/deletions")
def list_deletions(user_id: str | None = Query(None)):
    """列出删除请求记录."""
    results = _service.list_deletion_requests(user_id)
    return [
        {
            "request_id": r.request_id,
            "user_id": r.user_id,
            "total_deleted": r.total_deleted,
            "success": r.success,
            "completed_at": r.completed_at,
        }
        for r in results
    ]


@router.get("/deletions/{request_id}")
def get_deletion_proof(request_id: str):
    """获取删除证明."""
    result = _service.get_deletion_proof(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Deletion proof not found")
    return {
        "request_id": result.request_id,
        "user_id": result.user_id,
        "tenant_id": result.tenant_id,
        "deleted_counts": result.deleted_counts,
        "total_deleted": result.total_deleted,
        "errors": result.errors,
        "success": result.success,
        "completed_at": result.completed_at,
    }


# ─── PII 扫描/脱敏 ───────────────────────────────────────────────────────────


@router.post("/pii/scan", response_model=PIIScanResponse)
def scan_pii(req: PIIScanRequest):
    """扫描文本中的 PII."""
    scan_result = _detector.scan(req.text)
    return PIIScanResponse(
        has_pii=scan_result.has_pii,
        pii_count=scan_result.pii_count,
        matches=[
            {
                "type": m.pii_type.value,
                "value": m.value[:20] + "..." if len(m.value) > 20 else m.value,
                "start": m.start,
                "end": m.end,
                "confidence": m.confidence,
            }
            for m in scan_result.matches
        ],
    )


@router.post("/pii/mask", response_model=PIIMaskResponse)
def mask_pii(req: PIIMaskRequest):
    """脱敏文本中的 PII."""
    try:
        strategy = MaskStrategy(req.strategy)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy: {req.strategy}. Must be one of: mask, hash, remove, generalize",
        )
    masker = PIIMasker(default_strategy=strategy)
    result = masker.mask(req.text)
    return PIIMaskResponse(
        original_length=len(req.text),
        masked_text=result.masked_text,
        pii_count=result.pii_count,
    )


# ─── 数据驻留 ─────────────────────────────────────────────────────────────────


@router.get("/residency")
def get_residency():
    """获取数据驻留配置."""
    config = get_residency_config()
    return {
        "enabled": config.enabled,
        "default_region": config.default_region.value,
        "rules": {
            tid: {
                "region": r.region.value,
                "allowed_regions": [ar.value for ar in r.allowed_regions],
                "block_cross_border": r.block_cross_border,
            }
            for tid, r in config.rules.items()
        },
    }


@router.put("/residency/{tenant_id}", response_model=ResidencyRuleResponse)
def set_residency_rule(tenant_id: str, req: ResidencyRuleRequest):
    """设置租户数据驻留规则."""
    config = get_residency_config()
    try:
        region = DataRegion(req.region)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region: {req.region}. Must be one of: {[r.value for r in DataRegion]}",
        )
    allowed = []
    for ar in req.allowed_regions:
        try:
            allowed.append(DataRegion(ar))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid allowed_region: {ar}")

    rule = config.set_rule(tenant_id, region, allowed or None, req.block_cross_border)
    return ResidencyRuleResponse(
        tenant_id=tenant_id,
        region=rule.region.value,
        allowed_regions=[ar.value for ar in rule.allowed_regions],
        block_cross_border=rule.block_cross_border,
    )
