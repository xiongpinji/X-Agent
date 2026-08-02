"""Enhanced audit API endpoints with advanced search, analytics, and compliance reporting.

挂载状态: 本路由当前未挂载到 main.py(交集成波)。挂载前已具备:
- 全部租户相关端点强制 tenant 收敛(语义同
  ``backend.app.api.audit._enforce_audit_tenant_scope``):
  非 admin 传入他人 tenant_id → 403; 未传入 → 收敛到本租户;
  admin 可指定任意租户或不指定(跨租户全量)。
- 使用独立的增强审计存储 provider :func:`get_enhanced_audit_store`
  (dependencies.get_audit_store 返回的是 core.audit.AuditStore,
  缺少 search/get_analytics/generate_compliance_report/export_xml,
  直接复用会导致 500)。
"""

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from backend.app.api.errors import api_error
from backend.app.api.linked_summary import build_linked_summary
from backend.app.api.pagination import apply_pagination
from backend.app.core.audit_enhanced import (
    AuditChainVerification,
    AuditSearchCriteria,
    ComplianceReport,
)
from backend.app.core.audit_enhanced import (
    AuditStore as EnhancedAuditStore,
)
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


def _enforce_audit_tenant_scope(principal: Principal, tenant_id: str | None) -> str | None:
    """强制审计查询的租户边界。

    语义镜像 ``backend.app.api.audit._enforce_audit_tenant_scope``
    (本文件独立维护一份, 避免跨 API 模块引用私有函数在并行开发期被改动):
    - 非 admin 角色(含 viewer)只能访问本租户审计数据:
      显式传入与本租户不符的 tenant_id 视为越权, 返回 403;
      未传入时强制收敛到本租户。
    - admin 可指定任意租户过滤, 或不指定(跨租户全量)。
    """
    if principal.role == "admin":
        return tenant_id
    if tenant_id is not None and tenant_id != principal.tenant_id:
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "Access denied: cannot access audit logs of another tenant.",
        )
    return principal.tenant_id


@lru_cache
def get_enhanced_audit_store() -> EnhancedAuditStore:
    """增强审计存储 provider(挂载前自包含; 集成波可迁入 dependencies.py)。

    HMAC secret 处理与 ``backend.app.dependencies.get_audit_store`` 一致:
    生产环境缺失即 fail-fast; 开发/测试使用临时密钥并告警。

    存储路径默认使用独立文件 ``audit_enhanced.jsonl``(与基础
    audit.jsonl 的 AuditLogRecord schema 不同, 混写同一文件会破坏
    哈希链验证; 集成波如需统一存储, 需同步迁移基础存储的记录模型)。
    """
    settings = get_settings()
    hmac_secret = settings.audit_hmac_secret
    if not hmac_secret:
        if settings.app_mode == "production":
            raise RuntimeError(
                "audit_hmac_secret must be configured in production "
                "(set XAGENT_AUDIT_HMAC_SECRET; see .env.example)"
            )
        hmac_secret = token_urlsafe(32)
    storage_path = settings.audit_store_path.with_name("audit_enhanced.jsonl")
    return EnhancedAuditStore(storage_path=storage_path, hmac_secret=hmac_secret)


AuditStoreDependency = Annotated[EnhancedAuditStore, Depends(get_enhanced_audit_store)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/logs", response_model=dict[str, object])
async def list_audit_logs_enhanced(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: str | None = None,
    trace_id: str | None = None,
    run_id: str | None = None,
    workflow_id: str | None = None,
    has_snapshot: bool | None = None,
) -> dict[str, object]:
    """List audit logs with filtering and pagination.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        limit: Number of items per page
        offset: Number of items to skip
        tenant_id: Filter by tenant (non-admin 强制收敛到本租户)
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome
        trace_id: Filter by trace ID
        run_id: Filter by run ID
        workflow_id: Filter by workflow ID
        has_snapshot: Filter by snapshot presence

    Returns:
        Paginated audit logs
    """
    enforce_scope(principal, "audit:read")
    tenant_id = _enforce_audit_tenant_scope(principal, tenant_id)

    records = audit_store.list(
        limit=10000,
        offset=0,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
    )

    # Additional filtering
    filtered = [
        record
        for record in records
        if (trace_id is None or record.trace_id == trace_id)
        and (run_id is None or record.run_id == run_id)
        and (workflow_id is None or record.workflow_id == workflow_id)
        and (has_snapshot is None or bool(record.snapshot_before or record.snapshot_after) == has_snapshot)
    ]

    # Apply pagination
    paginated, metadata = apply_pagination(filtered, limit, offset)

    return {
        "data": [record.model_dump(mode="json") for record in paginated],
        "pagination": metadata.model_dump(),
    }


@router.get("/logs/{log_id}", response_model=dict[str, object])
async def get_audit_log(
    log_id: str,
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Get a specific audit log by ID.

    Args:
        log_id: Audit log ID
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)

    Returns:
        Audit log details
    """
    enforce_scope(principal, "audit:read")

    records = audit_store.list(limit=100000)
    for record in records:
        if record.id == log_id:
            # 非 admin 跨租户读取按越权处理(与查询端点的 tenant 语义一致)
            if principal.role != "admin" and record.tenant_id != principal.tenant_id:
                raise api_error(
                    403,
                    ErrorCode.AUTHORIZATION_FAILED,
                    "Access denied: cannot access audit logs of another tenant.",
                )
            return {
                "data": record.model_dump(mode="json"),
            }

    raise api_error(
        404,
        ErrorCode.RESOURCE_NOT_FOUND,
        "Audit log not found.",
        details={"log_id": log_id},
    )


@router.post("/search", response_model=dict[str, object])
async def search_audit_logs(
    criteria: AuditSearchCriteria,
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Advanced search with multiple criteria.

    Args:
        criteria: Search criteria (tenant_id 非 admin 强制收敛到本租户)
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)

    Returns:
        Search results with pagination
    """
    enforce_scope(principal, "audit:read")

    # 强制租户收敛: 显式传入他人 tenant_id → 403; 未传入 → 本租户
    criteria.tenant_id = _enforce_audit_tenant_scope(principal, criteria.tenant_id)

    records, total = audit_store.search(criteria)

    return {
        "data": [record.model_dump(mode="json") for record in records],
        "pagination": {
            "limit": criteria.limit,
            "offset": criteria.offset,
            "total": total,
            "has_more": criteria.offset + criteria.limit < total,
        },
    }


@router.get("/analytics", response_model=dict[str, object])
async def get_audit_analytics(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    tenant_id: str | None = None,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, object]:
    """Get audit analytics and insights.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        tenant_id: Filter by tenant (non-admin 强制收敛到本租户)
        days: Number of days to analyze

    Returns:
        Analytics data
    """
    enforce_scope(principal, "audit:read")
    tenant_id = _enforce_audit_tenant_scope(principal, tenant_id)

    start_time = datetime.now(UTC) - timedelta(days=days)
    analytics = audit_store.get_analytics(
        tenant_id=tenant_id,
        start_time=start_time,
    )

    return {
        "data": analytics.model_dump(mode="json"),
        "period": {
            "start": start_time.isoformat(),
            "end": datetime.now(UTC).isoformat(),
            "days": days,
        },
    }


@router.get("/reports/compliance", response_model=dict[str, object])
async def get_compliance_report(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    report_type: str = Query(default="SOC2"),
    days: int = Query(default=30, ge=1, le=365),
    tenant_id: str | None = None,
) -> dict[str, object]:
    """Generate compliance report.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        report_type: Type of compliance report (SOC2, ISO27001, GDPR, etc.)
        days: Number of days to include in report
        tenant_id: Filter by tenant (non-admin 强制收敛到本租户)

    Returns:
        Compliance report
    """
    enforce_scope(principal, "audit:read")
    tenant_id = _enforce_audit_tenant_scope(principal, tenant_id)

    period_start = datetime.now(UTC) - timedelta(days=days)
    period_end = datetime.now(UTC)

    report = audit_store.generate_compliance_report(
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        tenant_id=tenant_id,
    )

    return {
        "data": report.model_dump(mode="json"),
    }


@router.get("/verify", response_model=AuditChainVerification)
async def verify_audit_chain(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
) -> AuditChainVerification:
    """Verify audit chain integrity.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)

    Returns:
        Chain verification result
    """
    enforce_scope(principal, "audit:read")
    return audit_store.verify_chain()


@router.get("/summary")
async def audit_summary(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    tenant_id: str | None = None,
) -> dict[str, object]:
    """Get audit summary statistics.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        tenant_id: Filter by tenant (non-admin 强制收敛到本租户)

    Returns:
        Summary statistics
    """
    enforce_scope(principal, "audit:read")
    tenant_id = _enforce_audit_tenant_scope(principal, tenant_id)

    items = audit_store.list(limit=10000, tenant_id=tenant_id)

    by_action: dict[str, int] = {}
    by_resource_type: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    by_actor: dict[str, int] = {}

    for item in items:
        by_action[item.action] = by_action.get(item.action, 0) + 1
        by_resource_type[item.resource_type] = by_resource_type.get(item.resource_type, 0) + 1
        by_outcome[item.outcome] = by_outcome.get(item.outcome, 0) + 1
        by_actor[item.actor_id] = by_actor.get(item.actor_id, 0) + 1

    primary = {
        "count": len(items),
        "by_action": by_action,
        "by_resource_type": by_resource_type,
        "by_outcome": by_outcome,
        "by_actor": by_actor,
    }

    return build_linked_summary(
        resource_type="audit_summary",
        resource_id="audit_summary",
        primary=primary,
        audit=primary,
        extra=primary,
    )


@router.get("/export/csv")
async def export_audit_logs_csv(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    tenant_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: str | None = None,
) -> StreamingResponse:
    """Export audit logs as CSV file.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        tenant_id: Filter by tenant (non-admin 强制收敛到本租户)
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome

    Returns:
        CSV file as streaming response
    """
    enforce_scope(principal, "audit:read")
    tenant_id = _enforce_audit_tenant_scope(principal, tenant_id)

    csv_content = audit_store.export_csv(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
    )

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-logs.csv"},
    )


@router.get("/export/json")
async def export_audit_logs_json(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    tenant_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: str | None = None,
) -> dict[str, object]:
    """Export audit logs as JSON.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        tenant_id: Filter by tenant (non-admin 强制收敛到本租户)
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome

    Returns:
        JSON formatted audit logs
    """
    enforce_scope(principal, "audit:read")
    tenant_id = _enforce_audit_tenant_scope(principal, tenant_id)

    records = audit_store.export_json(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
    )

    return {
        "data": records,
        "count": len(records),
    }


@router.get("/export/xml")
async def export_audit_logs_xml(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    tenant_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: str | None = None,
) -> StreamingResponse:
    """Export audit logs as XML file.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        tenant_id: Filter by tenant (non-admin 强制收敛到本租户)
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome

    Returns:
        XML file as streaming response
    """
    enforce_scope(principal, "audit:read")
    tenant_id = _enforce_audit_tenant_scope(principal, tenant_id)

    xml_content = audit_store.export_xml(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
    )

    return StreamingResponse(
        iter([xml_content]),
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=audit-logs.xml"},
    )


@router.post("/export/pdf")
async def export_audit_logs_pdf(
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
    report_type: str = Query(default="SOC2"),
    days: int = Query(default=30, ge=1, le=365),
    tenant_id: str | None = None,
) -> StreamingResponse:
    """Export compliance report as PDF.

    Args:
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)
        report_type: Type of compliance report
        days: Number of days to include
        tenant_id: Filter by tenant (non-admin 强制收敛到本租户)

    Returns:
        PDF file as streaming response
    """
    enforce_scope(principal, "audit:read")
    tenant_id = _enforce_audit_tenant_scope(principal, tenant_id)

    period_start = datetime.now(UTC) - timedelta(days=days)
    period_end = datetime.now(UTC)

    report = audit_store.generate_compliance_report(
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        tenant_id=tenant_id,
    )

    # Generate PDF content; reportlab 缺失时显式 501, 不返回伪 PDF 内容
    pdf_content = _generate_pdf_report(report)

    return StreamingResponse(
        iter([pdf_content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=audit-report-{report_type}.pdf"},
    )


def _generate_pdf_report(report: ComplianceReport) -> bytes:
    """Generate PDF report from compliance report data.

    Raises:
        api_error(501): reportlab 未安装(显式降级, 不返回伪 PDF)。
    """
    try:
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise api_error(
            501,
            ErrorCode.INTERNAL_ERROR,
            "PDF export requires the reportlab package "
            "(pip install reportlab; listed in requirements.txt).",
        ) from exc

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=30,
    )
    elements.append(Paragraph(f"{report.report_type} Compliance Report", title_style))
    elements.append(Spacer(1, 0.2 * inch))

    # Report metadata
    metadata = [
        ["Report ID:", report.report_id],
        ["Generated:", report.generated_at.isoformat()],
        ["Period:", f"{report.period_start.date()} to {report.period_end.date()}"],
    ]
    metadata_table = Table(metadata, colWidths=[2 * inch, 4 * inch])
    metadata_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
    ]))
    elements.append(metadata_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Summary metrics
    elements.append(Paragraph("Summary Metrics", styles["Heading2"]))
    metrics = [
        ["Metric", "Value"],
        ["Total Operations", str(report.total_operations)],
        ["Successful", str(report.successful_operations)],
        ["Failed", str(report.failed_operations)],
        ["Denied", str(report.denied_operations)],
        ["Login Attempts", str(report.login_attempts)],
        ["Failed Logins", str(report.failed_logins)],
        ["Permission Changes", str(report.permission_changes)],
        ["Data Exports", str(report.data_exports)],
    ]
    metrics_table = Table(metrics, colWidths=[3 * inch, 2 * inch])
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Findings
    if report.findings:
        elements.append(Paragraph("Findings", styles["Heading2"]))
        for finding in report.findings:
            severity = finding.get("severity", "info").upper()
            description = finding.get("description", "")
            elements.append(Paragraph(f"<b>[{severity}]</b> {description}", styles["Normal"]))
        elements.append(Spacer(1, 0.2 * inch))

    # Recommendations
    if report.recommendations:
        elements.append(Paragraph("Recommendations", styles["Heading2"]))
        for i, rec in enumerate(report.recommendations, 1):
            elements.append(Paragraph(f"{i}. {rec}", styles["Normal"]))

    # Signature
    elements.append(Spacer(1, 0.3 * inch))
    signature = report.signature or ""
    elements.append(Paragraph(f"<b>Report Signature:</b> {signature[:32]}...", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
