from __future__ import annotations

from typing import Annotated
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.api.pagination import PaginationParams, apply_pagination
from backend.app.core.admin import TenantCreateRequest, TenantUpdateRequest, tenant_store
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal, get_audit_store

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.post("")
async def create_tenant(request: TenantCreateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return tenant_store.create(request).model_dump(mode="json")


@router.get("")
async def list_tenants(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return {"data": [item.model_dump(mode="json") for item in tenant_store.list()]}


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = tenant_store.get(tenant_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Tenant not found.", details={"resource_type": "tenant", "resource_id": tenant_id})
    return record.model_dump(mode="json")


@router.put("/{tenant_id}")
async def update_tenant(tenant_id: str, request: TenantUpdateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    return tenant_store.upsert(request, tenant_id).model_dump(mode="json")


@router.get("/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str,
    principal: PrincipalDependency,
    period: str = Query("month", regex="^(day|week|month|year)$"),
) -> dict[str, object]:
    """Get tenant usage statistics for the specified period.

    Returns metrics including:
    - Number of workflow runs
    - Number of agents created
    - Memory usage
    - API calls
    - Active users

    Args:
        tenant_id: Tenant ID
        principal: Current principal (must have security:manage scope)
        period: Time period for statistics (day, week, month, year)

    Returns:
        Usage statistics
    """
    enforce_scope(principal, "security:manage")
    record = tenant_store.get(tenant_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Tenant not found.", details={"resource_type": "tenant", "resource_id": tenant_id})

    # Calculate period dates
    now = datetime.now(UTC)
    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(weeks=1)
    elif period == "year":
        start_date = now - timedelta(days=365)
    else:  # month
        start_date = now - timedelta(days=30)

    # TODO: Query actual usage metrics from database
    # This would involve:
    # 1. Counting workflow runs for tenant in period
    # 2. Counting agents created in period
    # 3. Calculating memory usage
    # 4. Counting API calls
    # 5. Counting active users

    return {
        "tenant_id": tenant_id,
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": now.isoformat(),
        "usage": {
            "runs": 0,
            "agents": 0,
            "memory_gb": 0.0,
            "api_calls": 0,
            "active_users": 0,
        },
    }


@router.get("/{tenant_id}/billing")
async def get_tenant_billing(
    tenant_id: str,
    principal: PrincipalDependency,
    month: str | None = Query(None),
) -> dict[str, object]:
    """Get tenant billing information.

    Returns billing details including:
    - Current plan
    - Monthly charges
    - Usage-based costs
    - Payment status
    - Invoice history

    Args:
        tenant_id: Tenant ID
        principal: Current principal (must have security:manage scope)
        month: Specific month for billing (YYYY-MM format)

    Returns:
        Billing information
    """
    enforce_scope(principal, "security:manage")
    record = tenant_store.get(tenant_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Tenant not found.", details={"resource_type": "tenant", "resource_id": tenant_id})

    # Determine billing period
    # month 校验放在 handler 内（而非 Query regex 约束）：非法格式统一返回
    # 400 VALIDATION_ERROR 信封，而非 FastAPI 参数约束失败的 422 —— 与本项目
    # 业务级输入错误的契约一致(见 auth.login_oauth / verify_email)。
    if month:
        parts = month.split("-")
        if len(parts) != 2 or not (parts[0].isdigit() and len(parts[0]) == 4 and parts[1].isdigit() and len(parts[1]) == 2):
            raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid month format. Use YYYY-MM.")
        billing_month = f"{parts[0]}-{parts[1]}"
    else:
        now = datetime.now(UTC)
        billing_month = now.strftime("%Y-%m")

    # TODO: Query actual billing data from database
    # This would involve:
    # 1. Fetching plan details
    # 2. Calculating usage-based charges
    # 3. Retrieving payment status
    # 4. Generating invoice data

    return {
        "tenant_id": tenant_id,
        "plan": record.plan if hasattr(record, "plan") else "free",
        "billing_month": billing_month,
        "billing": {
            "plan_amount": 0.0,
            "usage_amount": 0.0,
            "total_amount": 0.0,
            "currency": "USD",
            "status": "paid",
        },
        "next_billing_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
    }


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str, principal: PrincipalDependency) -> dict[str, bool]:
    enforce_scope(principal, "security:manage")
    if not tenant_store.delete(tenant_id):
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Tenant not found.", details={"resource_type": "tenant", "resource_id": tenant_id})
    return {"deleted": True}
