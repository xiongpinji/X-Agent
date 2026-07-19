"""JWT密钥轮换API端点"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.jwt_key_rotation import JWTKeyRecord, JWTKeyRotationStore, get_jwt_key_store
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/security/jwt-keys", tags=["security"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
JWTKeyStoreDependency = Annotated[JWTKeyRotationStore, Depends(get_jwt_key_store)]


@router.get("", response_model=list[JWTKeyRecord])
async def list_jwt_keys(
    principal: PrincipalDependency,
    store: JWTKeyStoreDependency,
    include_inactive: bool = False,
) -> list[JWTKeyRecord]:
    """列出JWT密钥"""
    enforce_scope(principal, "security:manage")
    return store.list_keys(include_inactive=include_inactive)


@router.get("/primary", response_model=JWTKeyRecord)
async def get_primary_jwt_key(
    principal: PrincipalDependency,
    store: JWTKeyStoreDependency,
) -> JWTKeyRecord:
    """获取主JWT密钥"""
    enforce_scope(principal, "security:manage")
    key = store.get_primary_key()
    if key is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Primary JWT key not found.")
    return key


@router.get("/active", response_model=list[JWTKeyRecord])
async def get_active_jwt_keys(
    principal: PrincipalDependency,
    store: JWTKeyStoreDependency,
) -> list[JWTKeyRecord]:
    """获取所有活跃JWT密钥"""
    enforce_scope(principal, "security:manage")
    return store.get_active_keys()


@router.post("/rotate", response_model=JWTKeyRecord)
async def rotate_jwt_key(
    principal: PrincipalDependency,
    store: JWTKeyStoreDependency,
    reason: str = "Manual rotation",
) -> JWTKeyRecord:
    """轮换JWT密钥"""
    enforce_scope(principal, "security:manage")
    new_key = store.rotate_key(reason=reason)
    return new_key


@router.post("/{key_id}/revoke", response_model=dict[str, bool])
async def revoke_jwt_key(
    key_id: str,
    principal: PrincipalDependency,
    store: JWTKeyStoreDependency,
    reason: str = "Manual revocation",
) -> dict[str, bool]:
    """撤销JWT密钥"""
    enforce_scope(principal, "security:manage")
    success = store.revoke_key(key_id, reason=reason)
    if not success:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "JWT key not found.")
    return {"revoked": True}


@router.get("/rotation-status", response_model=dict[str, object])
async def get_rotation_status(
    principal: PrincipalDependency,
    store: JWTKeyStoreDependency,
) -> dict[str, object]:
    """获取密钥轮换状态"""
    enforce_scope(principal, "security:manage")
    primary_key = store.get_primary_key()
    should_rotate = store.should_rotate()
    return {
        "primary_key_id": primary_key.key_id if primary_key else None,
        "primary_key_age_days": (
            (datetime.now(UTC) - primary_key.created_at).days if primary_key else None
        ),
        "should_rotate": should_rotate,
        "active_keys_count": len(store.get_active_keys()),
        "total_keys_count": len(store.list_keys(include_inactive=True)),
    }


from datetime import UTC, datetime
