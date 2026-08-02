"""Enterprise IM Integration API Endpoints"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.integrations.enterprise.base import MessageType
from backend.app.integrations.enterprise.manager import EnterpriseIMManager
from backend.app.integrations.enterprise.message_router import MessageRouter
from backend.app.integrations.enterprise.user_mapping import UserMapping

router = APIRouter(prefix="/api/v1/enterprise-im", tags=["enterprise-im"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Global instances
_manager = EnterpriseIMManager()
_router = MessageRouter(_manager)
_user_mapping = UserMapping()


# Request/Response Models
class PlatformConfigRequest(BaseModel):
    """Platform configuration request"""
    platform: str = Field(..., min_length=1, max_length=50)
    credentials: dict[str, str] = Field(...)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class SendMessageRequest(BaseModel):
    """Send message request"""
    platform: str = Field(..., min_length=1, max_length=50)
    user_id: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=10000)
    msg_type: str = Field(default="text", pattern="^(text|markdown|card)$")


class SendCardRequest(BaseModel):
    """Send card message request"""
    platform: str = Field(..., min_length=1, max_length=50)
    user_id: str = Field(..., min_length=1, max_length=200)
    card: dict[str, Any] = Field(...)


class BroadcastMessageRequest(BaseModel):
    """Broadcast message request"""
    platforms: list[str] = Field(default_factory=list)
    message: str = Field(..., min_length=1, max_length=10000)
    msg_type: str = Field(default="text", pattern="^(text|markdown|card)$")


class CreateApprovalRequest(BaseModel):
    """Create approval request"""
    platform: str = Field(..., min_length=1, max_length=50)
    template_id: str = Field(..., min_length=1, max_length=200)
    data: dict[str, Any] = Field(...)


class UserMappingRequest(BaseModel):
    """User mapping request"""
    internal_user_id: str = Field(..., min_length=1, max_length=200)
    platform: str = Field(..., min_length=1, max_length=50)
    platform_user_id: str = Field(..., min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Platform Configuration Endpoints
@router.post("/platforms/configure")
async def configure_platform(
    request: PlatformConfigRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Configure a platform"""
    enforce_scope(principal, "security:manage")

    try:
        platform = request.platform.lower()

        if platform == "dingtalk":
            success = await _manager.create_dingtalk_platform(
                app_key=request.credentials.get("app_key", ""),
                app_secret=request.credentials.get("app_secret", ""),
                corp_id=request.credentials.get("corp_id"),
            )
        elif platform == "feishu":
            success = await _manager.create_feishu_platform(
                app_id=request.credentials.get("app_id", ""),
                app_secret=request.credentials.get("app_secret", ""),
            )
        elif platform == "wechat_work":
            success = await _manager.create_wechat_work_platform(
                corp_id=request.credentials.get("corp_id", ""),
                corp_secret=request.credentials.get("corp_secret", ""),
                agent_id=request.credentials.get("agent_id"),
            )
        else:
            raise api_error(400, ErrorCode.INVALID_REQUEST, f"Unsupported platform: {platform}")

        if not success:
            raise api_error(400, ErrorCode.INVALID_REQUEST, "Failed to authenticate with platform")

        return {
            "platform": platform,
            "configured": True,
            "status": _manager.get_platform(platform).get_connection_status() if _manager.get_platform(platform) else {},
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/platforms")
async def list_platforms(
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """List all configured platforms"""
    enforce_scope(principal, "security:manage")

    platforms = _manager.list_platforms()
    status_info = _manager.get_connection_status_all()

    return {
        "platforms": platforms,
        "status": status_info,
    }


@router.get("/platforms/{platform}/status")
async def get_platform_status(
    platform: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Get platform status"""
    enforce_scope(principal, "security:manage")

    plat = _manager.get_platform(platform)
    if not plat:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, f"Platform not found: {platform}")

    return plat.get_connection_status()


@router.post("/platforms/{platform}/health-check")
async def health_check_platform(
    platform: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Check platform health"""
    enforce_scope(principal, "security:manage")

    plat = _manager.get_platform(platform)
    if not plat:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, f"Platform not found: {platform}")

    try:
        healthy = await plat.health_check()
        return {
            "platform": platform,
            "healthy": healthy,
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


# Message Sending Endpoints
@router.post("/messages/send")
async def send_message(
    request: SendMessageRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Send a message to a user"""
    enforce_scope(principal, "security:manage")

    try:
        msg_type = MessageType(request.msg_type)
        success = await _manager.send_message_to_platform(
            request.platform,
            request.user_id,
            request.message,
            msg_type,
        )

        return {
            "platform": request.platform,
            "user_id": request.user_id,
            "sent": success,
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/messages/broadcast")
async def broadcast_message(
    request: BroadcastMessageRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Broadcast a message to all users"""
    enforce_scope(principal, "security:manage")

    try:
        msg_type = MessageType(request.msg_type)
        platforms = request.platforms or _manager.list_platforms()

        results = await _router.broadcast_message(
            request.message,
            platforms,
            msg_type=msg_type,
        )

        return {
            "platforms": platforms,
            "results": results,
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/messages/card")
async def send_card(
    request: SendCardRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Send a card message"""
    enforce_scope(principal, "security:manage")

    try:
        success = await _manager.send_card_to_platform(
            request.platform,
            request.user_id,
            request.card,
        )

        return {
            "platform": request.platform,
            "user_id": request.user_id,
            "sent": success,
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


# Contacts Endpoints
@router.post("/contacts/sync")
async def sync_contacts(
    platform: str | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Sync contacts from platforms"""
    enforce_scope(principal, "security:manage")

    try:
        if platform:
            plat = _manager.get_platform(platform)
            if not plat:
                raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, f"Platform not found: {platform}")

            contacts = await plat.sync_contacts()
            await _user_mapping.bulk_sync_users(platform, contacts)

            return {
                "platform": platform,
                "synced": len(contacts),
            }
        else:
            results = {}
            for plat_name in _manager.list_platforms():
                plat = _manager.get_platform(plat_name)
                contacts = await plat.sync_contacts()
                sync_result = await _user_mapping.bulk_sync_users(plat_name, contacts)
                results[plat_name] = sync_result

            return {
                "platforms": results,
            }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/contacts/users")
async def list_users(
    platform: str | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """List users"""
    enforce_scope(principal, "security:manage")

    try:
        if platform:
            users = await _user_mapping.get_users_by_platform(platform)
        else:
            users = await _user_mapping.get_all_users()

        return {
            "users": users,
            "total": len(users),
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/contacts/departments")
async def list_departments(
    platform: str | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """List departments"""
    enforce_scope(principal, "security:manage")

    try:
        if platform:
            plat = _manager.get_platform(platform)
            if not plat:
                raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, f"Platform not found: {platform}")

            departments = await plat.sync_departments()
            return {
                "platform": platform,
                "departments": departments,
            }
        else:
            results = {}
            for plat_name in _manager.list_platforms():
                plat = _manager.get_platform(plat_name)
                departments = await plat.sync_departments()
                results[plat_name] = departments

            return {
                "platforms": results,
            }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


# Approval Endpoints
@router.post("/approvals")
async def create_approval(
    request: CreateApprovalRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Create an approval"""
    enforce_scope(principal, "security:manage")

    try:
        approval_id = await _manager.create_approval_on_platform(
            request.platform,
            request.template_id,
            request.data,
        )

        if not approval_id:
            raise api_error(400, ErrorCode.INVALID_REQUEST, "Failed to create approval")

        return {
            "platform": request.platform,
            "approval_id": approval_id,
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    platform: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Get approval status"""
    enforce_scope(principal, "security:manage")

    try:
        status = await _manager.get_approval_status_from_platform(platform, approval_id)

        if not status:
            raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Approval not found")

        return {
            "platform": platform,
            "approval_id": approval_id,
            "status": status,
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


# User Mapping Endpoints
@router.post("/users/map")
async def map_user(
    request: UserMappingRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Map a user across platforms"""
    enforce_scope(principal, "security:manage")

    try:
        success = await _user_mapping.map_user(
            request.internal_user_id,
            request.platform,
            request.platform_user_id,
            request.metadata,
        )

        if not success:
            raise api_error(400, ErrorCode.INVALID_REQUEST, "Failed to map user")

        return {
            "internal_user_id": request.internal_user_id,
            "platform": request.platform,
            "platform_user_id": request.platform_user_id,
            "mapped": True,
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/users/{internal_user_id}/mappings")
async def get_user_mappings(
    internal_user_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Get user mappings"""
    enforce_scope(principal, "security:manage")

    try:
        mappings = await _user_mapping.get_user_mappings(internal_user_id)
        metadata = await _user_mapping.get_user_metadata(internal_user_id)

        return {
            "internal_user_id": internal_user_id,
            "mappings": mappings,
            "metadata": metadata,
        }
    except Exception as e:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, str(e))


# Statistics Endpoints
@router.get("/stats/delivery")
async def get_delivery_stats(
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Get message delivery statistics"""
    enforce_scope(principal, "security:manage")

    return {
        "overall": _router.get_delivery_stats(),
        "by_platform": _router.get_platform_stats(),
    }


@router.get("/stats/mapping")
async def get_mapping_stats(
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Get user mapping statistics"""
    enforce_scope(principal, "security:manage")

    return _user_mapping.get_mapping_stats()


@router.get("/stats/sync")
async def get_sync_stats(
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Get sync statistics"""
    enforce_scope(principal, "security:manage")

    return _user_mapping.get_sync_stats()
