"""
企业级审计日志API路由
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.app.core.enterprise_audit import (
    AuditAnalyzer,
    AuditEventType,
    AuditLogEntry,
    AuditLogFilter,
    AuditLogStore,
    AuditSeverity,
    DashboardDataProvider,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/enterprise/audit", tags=["enterprise-audit"])

# 初始化管理器
audit_log_store = AuditLogStore()
audit_analyzer = AuditAnalyzer(audit_log_store)
dashboard_provider = DashboardDataProvider(audit_log_store, audit_analyzer)


class AuditLogQueryRequest(BaseModel):
    """审计日志查询请求"""
    tenant_id: str
    user_id: Optional[str] = None
    event_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = 100
    offset: int = 0


class AuditLogCreateRequest(BaseModel):
    """审计日志创建请求"""
    tenant_id: str
    event_type: str
    action: str
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    status: str = "success"
    details: dict[str, Any] = {}


@router.post("/logs/create", response_model=dict[str, Any])
async def create_audit_log(request: AuditLogCreateRequest) -> dict[str, Any]:
    """创建审计日志"""
    try:
        entry = AuditLogEntry(
            event_type=AuditEventType(request.event_type),
            tenant_id=request.tenant_id,
            action=request.action,
            user_id=request.user_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            status=request.status,
            details=request.details,
        )
        audit_log_store.append_log(entry)

        return {
            "status": "success",
            "log_id": entry.log_id,
            "message": "Audit log created successfully",
        }
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/logs/query", response_model=dict[str, Any])
async def query_audit_logs(request: AuditLogQueryRequest) -> dict[str, Any]:
    """查询审计日志"""
    try:
        filter = AuditLogFilter(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            limit=request.limit,
            offset=request.offset,
        )
        logs, total = audit_log_store.query_logs(filter)

        return {
            "status": "success",
            "total": total,
            "logs": [log.dict() for log in logs],
        }
    except Exception as e:
        logger.error(f"Failed to query audit logs: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/logs/{log_id}", response_model=dict[str, Any])
async def get_audit_log(log_id: str) -> dict[str, Any]:
    """获取单条审计日志"""
    try:
        log = audit_log_store.get_log(log_id)
        if not log:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")

        return {
            "status": "success",
            "log": log.dict(),
        }
    except Exception as e:
        logger.error(f"Failed to get audit log: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/dashboard", response_model=dict[str, Any])
async def get_audit_dashboard(tenant_id: str = Query(...)) -> dict[str, Any]:
    """获取审计仪表板"""
    try:
        metrics = dashboard_provider.get_dashboard_metrics(tenant_id)
        return {
            "status": "success",
            "metrics": metrics.dict(),
        }
    except Exception as e:
        logger.error(f"Failed to get audit dashboard: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/suspicious-activities", response_model=dict[str, Any])
async def get_suspicious_activities(tenant_id: str = Query(...)) -> dict[str, Any]:
    """获取可疑活动"""
    try:
        activities = audit_analyzer.detect_suspicious_activity(tenant_id)
        return {
            "status": "success",
            "activities": activities,
        }
    except Exception as e:
        logger.error(f"Failed to get suspicious activities: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/compliance-report", response_model=dict[str, Any])
async def generate_compliance_report(
    tenant_id: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
) -> dict[str, Any]:
    """生成合规报告"""
    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        report = audit_analyzer.generate_compliance_report(tenant_id, start, end)
        return {
            "status": "success",
            "report": report,
        }
    except Exception as e:
        logger.error(f"Failed to generate compliance report: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/user-activity/{user_id}", response_model=dict[str, Any])
async def get_user_activity(user_id: str, tenant_id: str = Query(...)) -> dict[str, Any]:
    """获取用户活动摘要"""
    try:
        summary = audit_log_store.get_user_activity_summary(user_id)
        return {
            "status": "success",
            "summary": summary,
        }
    except Exception as e:
        logger.error(f"Failed to get user activity: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/resource-audit-trail/{resource_id}", response_model=dict[str, Any])
async def get_resource_audit_trail(resource_id: str) -> dict[str, Any]:
    """获取资源审计跟踪"""
    try:
        trail = audit_log_store.get_resource_audit_trail(resource_id)
        return {
            "status": "success",
            "trail": [log.dict() for log in trail],
        }
    except Exception as e:
        logger.error(f"Failed to get resource audit trail: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/verify-chain", response_model=dict[str, Any])
async def verify_log_chain(start_log_id: Optional[str] = None) -> dict[str, Any]:
    """验证日志链完整性"""
    try:
        is_valid = audit_log_store.verify_log_chain(start_log_id)
        return {
            "status": "success",
            "chain_valid": is_valid,
        }
    except Exception as e:
        logger.error(f"Failed to verify log chain: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
