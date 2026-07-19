"""Enhanced audit API endpoints with advanced search, analytics, and compliance reporting."""

from typing import Annotated
from datetime import datetime, UTC, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from backend.app.api.linked_summary import LinkedSummaryEnvelope, build_linked_summary
from backend.app.api.pagination import PaginationParams, apply_pagination
from backend.app.core.audit_enhanced import (
    AuditStore,
    AuditSearchCriteria,
    AuditChainVerification,
    AuditLogRecord,
    ComplianceReport,
    AuditAnalytics,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_audit_store, get_current_principal

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/logs", response_model=dict[str, object])
async def list_audit_logs(
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
        tenant_id: Filter by tenant
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
            return {
                "data": record.model_dump(mode="json"),
            }

    return {
        "error": "Audit log not found",
        "log_id": log_id,
    }


@router.post("/search", response_model=dict[str, object])
async def search_audit_logs(
    criteria: AuditSearchCriteria,
    audit_store: AuditStoreDependency,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Advanced search with multiple criteria.

    Args:
        criteria: Search criteria
        audit_store: Audit store dependency
        principal: Current principal (must have audit:read scope)

    Returns:
        Search results with pagination
    """
    enforce_scope(principal, "audit:read")

    # Enforce tenant isolation
    if criteria.tenant_id is None:
        criteria.tenant_id = principal.tenant_id

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
        tenant_id: Filter by tenant (defaults to current tenant)
        days: Number of days to analyze

    Returns:
        Analytics data
    """
    enforce_scope(principal, "audit:read")

    if tenant_id is None:
        tenant_id = principal.tenant_id

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
        tenant_id: Filter by tenant (defaults to current tenant)

    Returns:
        Compliance report
    """
    enforce_scope(principal, "audit:read")

    if tenant_id is None:
        tenant_id = principal.tenant_id

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
        tenant_id: Filter by tenant (defaults to current tenant)

    Returns:
        Summary statistics
    """
    enforce_scope(principal, "audit:read")

    if tenant_id is None:
        tenant_id = principal.tenant_id

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
        tenant_id: Filter by tenant
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome

    Returns:
        CSV file as streaming response
    """
    enforce_scope(principal, "audit:read")

    if tenant_id is None:
        tenant_id = principal.tenant_id

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
        tenant_id: Filter by tenant
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome

    Returns:
        JSON formatted audit logs
    """
    enforce_scope(principal, "audit:read")

    if tenant_id is None:
        tenant_id = principal.tenant_id

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
        tenant_id: Filter by tenant
        actor_id: Filter by actor
        action: Filter by action
        resource_type: Filter by resource type
        outcome: Filter by outcome

    Returns:
        XML file as streaming response
    """
    enforce_scope(principal, "audit:read")

    if tenant_id is None:
        tenant_id = principal.tenant_id

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
        tenant_id: Filter by tenant

    Returns:
        PDF file as streaming response
    """
    enforce_scope(principal, "audit:read")

    if tenant_id is None:
        tenant_id = principal.tenant_id

    period_start = datetime.now(UTC) - timedelta(days=days)
    period_end = datetime.now(UTC)

    report = audit_store.generate_compliance_report(
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        tenant_id=tenant_id,
    )

    # Generate PDF content
    pdf_content = _generate_pdf_report(report)

    return StreamingResponse(
        iter([pdf_content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=audit-report-{report_type}.pdf"},
    )


def _generate_pdf_report(report: ComplianceReport) -> bytes:
    """Generate PDF report from compliance report data."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from io import BytesIO

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
        elements.append(Paragraph(f"<b>Report Signature:</b> {report.signature[:32]}...", styles["Normal"]))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    except ImportError:
        # Fallback if reportlab is not installed
        return b"PDF generation requires reportlab library"
