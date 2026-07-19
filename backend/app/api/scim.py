"""SCIM 2.0 用户 provisioning API (RFC 7643/7644, P1-02)。

实现范围:
- ``/scim/v2/Users`` 完整 CRUD: 创建 (POST)、查询 (GET 列表+过滤+分页 /
  GET 单条)、全量更新 (PUT)、部分更新 (PATCH)、停用 (DELETE → 软停用,
  is_active=False, 记录保留用于审计)。
- ``/scim/v2/ServiceProviderConfig``、``/scim/v2/ResourceTypes``、
  ``/scim/v2/Schemas`` 发现端点 (内容按真实能力声明)。
- Bearer token 鉴权 + 租户绑定: 每个 SCIM 令牌绑定一个 tenant_id,
  所有操作强制限定在该租户内 (跨租户访问一律 404, 不泄露存在性)。

令牌配置 (两种方式):
1. 环境变量 ``XAGENT_SCIM_TOKENS``: JSON 对象
   ``{"<token>": {"tenant_id": "t1", "description": "..."}}`` 或 JSON 数组
   ``[{"token": "...", "tenant_id": "t1"}]``。
2. 程序化: ``SCIMTokenRegistry.register(token, tenant_id)`` / 测试用
   ``build_scim_router(adapter=..., registry=...)`` 工厂注入。

存储层: 经 core.saml_sso.UserStoreAdapter 惰性桥接
``backend.app.models.user_store`` (存储层正被另一代理 Postgres 化,
本模块面向其现有接口编程, 不修改对方文件); 不可用时显式降级为内存后端
(日志 WARNING + adapter.mode == "memory")。

自包含: 不依赖 main.py, 可直接 ``app.include_router(router)``。
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.app.core.saml_sso import (
    SSOStorageError,
    UserRecord,
    UserStoreAdapter,
)

logger = logging.getLogger(__name__)

SCIM_CONTENT_TYPE = "application/scim+json"
SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
SCIM_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


# ============================================================================
# SCIM 错误响应 (RFC 7644 §3.12)
# ============================================================================

def scim_error(status: int, detail: str, scim_type: Optional[str] = None) -> JSONResponse:
    body: Dict[str, Any] = {
        "schemas": [SCIM_ERROR_SCHEMA],
        "status": str(status),
        "detail": detail,
    }
    if scim_type:
        body["scimType"] = scim_type
    headers = {}
    if status == 401:
        headers["WWW-Authenticate"] = 'Bearer realm="scim"'
    return JSONResponse(status_code=status, content=body, media_type=SCIM_CONTENT_TYPE, headers=headers)


def scim_json(body: Any, status: int = 200, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=body, media_type=SCIM_CONTENT_TYPE, headers=headers)


# ============================================================================
# Bearer token 鉴权 + 租户绑定
# ============================================================================

@dataclass
class SCIMTokenInfo:
    tenant_id: str
    token_prefix: str
    description: str = ""


class SCIMTokenRegistry:
    """SCIM bearer 令牌注册表 (令牌 → 租户绑定)。

    fail-closed: 注册表为空时所有请求一律 503, 绝不匿名放行。
    比较使用 hmac.compare_digest (常数时间, 防时序侧信道)。
    """

    def __init__(self) -> None:
        self._tokens: Dict[str, SCIMTokenInfo] = {}

    def register(self, token: str, tenant_id: str, description: str = "") -> None:
        if not token or not tenant_id:
            raise ValueError("SCIM token 与 tenant_id 均不能为空")
        self._tokens[token] = SCIMTokenInfo(
            tenant_id=tenant_id, token_prefix=token[:8], description=description
        )

    @property
    def configured(self) -> bool:
        return bool(self._tokens)

    def authenticate(self, token: str) -> Optional[SCIMTokenInfo]:
        for registered, info in self._tokens.items():
            if hmac.compare_digest(registered, token):
                return info
        return None

    def load_from_env(self, env_var: str = "XAGENT_SCIM_TOKENS") -> int:
        """从环境变量加载令牌 (JSON 对象或数组)。配置错误显式记日志并跳过。"""
        raw = os.environ.get(env_var, "").strip()
        if not raw:
            return 0
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            logger.error("%s 解析失败: %s — 跳过 env 令牌加载。", env_var, exc)
            return 0

        loaded = 0
        if isinstance(parsed, dict):
            items = [
                (token, conf.get("tenant_id"), conf.get("description", ""))
                for token, conf in parsed.items()
                if isinstance(conf, dict)
            ]
        elif isinstance(parsed, list):
            items = [
                (entry.get("token"), entry.get("tenant_id"), entry.get("description", ""))
                for entry in parsed
                if isinstance(entry, dict)
            ]
        else:
            logger.error("%s 顶层必须是 JSON 对象或数组。", env_var)
            return 0

        for token, tenant_id, description in items:
            if not token or not tenant_id:
                logger.error("%s 中存在缺 token/tenant_id 的条目 — 已跳过。", env_var)
                continue
            self.register(token, tenant_id, description or "")
            loaded += 1
        return loaded


# ============================================================================
# SCIM User 资源 ↔ 存储层映射
# ============================================================================

def record_to_scim_user(record: UserRecord, request: Request) -> Dict[str, Any]:
    scim_meta = (record.metadata or {}).get("scim", {})
    base = str(request.base_url).rstrip("/")
    return {
        "schemas": [SCIM_USER_SCHEMA],
        "id": record.user_id,
        "externalId": scim_meta.get("externalId"),
        "userName": record.email,
        "name": scim_meta.get("name") or (
            {"formatted": record.full_name} if record.full_name else {}
        ),
        "emails": scim_meta.get("emails") or [
            {"value": record.email, "type": "work", "primary": True}
        ],
        "active": record.is_active,
        "meta": {
            "resourceType": "User",
            "created": record.created_at,
            "lastModified": record.updated_at or record.created_at,
            "location": f"{base}/scim/v2/Users/{record.user_id}",
        },
    }


def _extract_scim_payload(payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Optional[str], bool]:
    """从 SCIM User payload 提取 (userName, scim_meta, full_name, active)。"""
    user_name = str(payload.get("userName") or "").strip()
    if not user_name:
        raise ValueError("userName 为必填字段。")

    name = payload.get("name") or {}
    if not isinstance(name, dict):
        raise ValueError("name 必须是对象。")
    full_name = name.get("formatted") or " ".join(
        part for part in [name.get("givenName"), name.get("familyName")] if part
    ) or None

    active = payload.get("active", True)
    if not isinstance(active, bool):
        raise ValueError("active 必须是布尔值。")

    emails = payload.get("emails")
    if emails is not None:
        if not isinstance(emails, list) or any(not isinstance(e, dict) or not e.get("value") for e in emails):
            raise ValueError("emails 必须是含 value 的对象数组。")

    scim_meta = {
        "externalId": payload.get("externalId"),
        "name": name,
        "emails": emails,
        "raw_schemas": payload.get("schemas"),
    }
    return user_name, scim_meta, full_name, active


# ============================================================================
# 过滤与分页
# ============================================================================

_FILTER_RE = re.compile(
    r'^\s*(userName|externalId)\s+eq\s+"([^"]*)"\s*$', re.IGNORECASE
)


def _parse_filter(filter_str: Optional[str]) -> Optional[Tuple[str, str]]:
    """解析 SCIM filter (支持 userName/externalId 的 eq; 其余显式报错)。"""
    if not filter_str:
        return None
    match = _FILTER_RE.match(filter_str)
    if not match:
        raise ValueError(
            "仅支持 `userName eq \"...\"` 与 `externalId eq \"...\"` 过滤表达式。"
        )
    return match.group(1).lower(), match.group(2)


def _matches_filter(record: UserRecord, parsed: Optional[Tuple[str, str]]) -> bool:
    if parsed is None:
        return True
    attr, value = parsed
    if attr == "username":
        return record.email.lower() == value.lower()
    if attr == "externalid":
        return (record.metadata or {}).get("scim", {}).get("externalId") == value
    return False


# ============================================================================
# Router 工厂 (测试/集成注入点)
# ============================================================================

def build_scim_router(
    adapter: Optional[UserStoreAdapter] = None,
    registry: Optional[SCIMTokenRegistry] = None,
) -> APIRouter:
    """构建 SCIM router。

    Args:
        adapter: 用户存储适配器 (None → 惰性 Postgres/内存降级)。
        registry: 令牌注册表 (None → 从 env 加载的空注册表, fail-closed)。
    """
    user_adapter = adapter or UserStoreAdapter()
    token_registry = registry or SCIMTokenRegistry()
    if registry is None:
        token_registry.load_from_env()

    router = APIRouter(prefix="/scim/v2", tags=["scim"])

    # ------------------------------------------------------------- 鉴权

    async def _auth(request: Request) -> "SCIMTokenInfo | JSONResponse":
        if not token_registry.configured:
            logger.error("SCIM 请求被拒绝: 未配置任何 SCIM 令牌 (fail-closed)。")
            return scim_error(
                503,
                "SCIM 服务未配置令牌 (XAGENT_SCIM_TOKENS), 拒绝所有请求 (fail-closed)。",
            )
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            return scim_error(401, "缺少或非法的 Authorization: Bearer <token> 头。")
        info = token_registry.authenticate(parts[1].strip())
        if info is None:
            return scim_error(401, "Bearer 令牌无效。")
        return info

    async def _get_tenant_user(user_id: str, tenant_id: str) -> Optional[UserRecord]:
        """按 id 取用户并强制租户匹配 (跨租户 → None → 404, 不泄露存在性)。"""
        record = await user_adapter.get_user_by_id(user_id)
        if record is None or record.tenant_id != tenant_id:
            return None
        return record

    # ------------------------------------------------------------- Users

    @router.get("/Users", include_in_schema=True)
    async def list_users(
        request: Request,
        filter: Optional[str] = None,
        startIndex: int = 1,
        count: int = 100,
    ) -> JSONResponse:
        auth = await _auth(request)
        if isinstance(auth, JSONResponse):
            return auth

        try:
            parsed = _parse_filter(filter)
        except ValueError as exc:
            return scim_error(400, str(exc), scim_type="invalidFilter")

        if startIndex < 1:
            return scim_error(400, "startIndex 必须 >= 1。", scim_type="invalidValue")
        if count < 0:
            return scim_error(400, "count 必须 >= 0。", scim_type="invalidValue")
        count = min(count, 500)

        try:
            if parsed and parsed[0] == "username":
                found = await user_adapter.get_user_by_email(parsed[1], auth.tenant_id)
                all_records = [found] if found else []
            else:
                # externalId 过滤 / 无过滤: 拉取租户全量后内存过滤
                # (用户量级受租户规模限制; 存储层后续支持 metadata 查询时下推)
                all_records = await user_adapter.list_users(
                    tenant_id=auth.tenant_id, skip=0, limit=100_000
                )
            matched = [r for r in all_records if _matches_filter(r, parsed)]
        except SSOStorageError as exc:
            logger.error("SCIM list 存储错误: %s", exc)
            return scim_error(503, f"用户存储不可用: {exc}")

        total = len(matched)
        page = matched[startIndex - 1: startIndex - 1 + count] if count else []
        return scim_json(
            {
                "schemas": [SCIM_LIST_SCHEMA],
                "totalResults": total,
                "startIndex": startIndex,
                "itemsPerPage": len(page),
                "Resources": [record_to_scim_user(r, request) for r in page],
            }
        )

    @router.post("/Users", status_code=201)
    async def create_user(request: Request) -> JSONResponse:
        auth = await _auth(request)
        if isinstance(auth, JSONResponse):
            return auth

        try:
            payload = await request.json()
        except Exception:
            return scim_error(400, "请求体必须是合法 JSON。")
        if not isinstance(payload, dict):
            return scim_error(400, "请求体必须是 JSON 对象。")

        try:
            user_name, scim_meta, full_name, active = _extract_scim_payload(payload)
        except ValueError as exc:
            return scim_error(400, str(exc), scim_type="invalidValue")

        try:
            existing = await user_adapter.get_user_by_email(user_name, auth.tenant_id)
            if existing is not None:
                return scim_error(
                    409, f"userName 已存在: {user_name}", scim_type="uniqueness"
                )
            record = await user_adapter.create_user(
                email=user_name,
                tenant_id=auth.tenant_id,
                full_name=full_name,
                role="user",
                metadata={"scim": scim_meta, "provisioned_by": "scim"},
            )
            if not active:
                await user_adapter.deactivate_user(record.user_id)
                record = await user_adapter.get_user_by_id(record.user_id) or record
        except SSOStorageError as exc:
            message = str(exc)
            if "已存在" in message or "unique" in message.lower() or "duplicate" in message.lower():
                return scim_error(409, message, scim_type="uniqueness")
            logger.error("SCIM create 存储错误: %s", exc)
            return scim_error(503, f"用户存储不可用: {exc}")

        location = f"{str(request.base_url).rstrip('/')}/scim/v2/Users/{record.user_id}"
        logger.info(
            "SCIM: 创建用户 %s (tenant=%s, token=%s…)",
            record.user_id, auth.tenant_id, auth.token_prefix,
        )
        return scim_json(
            record_to_scim_user(record, request), status=201, headers={"Location": location}
        )

    @router.get("/Users/{user_id}")
    async def get_user(user_id: str, request: Request) -> JSONResponse:
        auth = await _auth(request)
        if isinstance(auth, JSONResponse):
            return auth
        try:
            record = await _get_tenant_user(user_id, auth.tenant_id)
        except SSOStorageError as exc:
            logger.error("SCIM get 存储错误: %s", exc)
            return scim_error(503, f"用户存储不可用: {exc}")
        if record is None:
            return scim_error(404, f"User 不存在: {user_id}")
        return scim_json(record_to_scim_user(record, request))

    @router.put("/Users/{user_id}")
    async def replace_user(user_id: str, request: Request) -> JSONResponse:
        auth = await _auth(request)
        if isinstance(auth, JSONResponse):
            return auth

        record = await _get_tenant_user(user_id, auth.tenant_id)
        if record is None:
            return scim_error(404, f"User 不存在: {user_id}")

        try:
            payload = await request.json()
        except Exception:
            return scim_error(400, "请求体必须是合法 JSON。")
        try:
            user_name, scim_meta, full_name, active = _extract_scim_payload(payload)
        except ValueError as exc:
            return scim_error(400, str(exc), scim_type="invalidValue")

        # userName(=email) 变更: 存储层 update_user 不允许改 email — 显式报错而非静默忽略
        if user_name.lower() != record.email.lower():
            conflict = await user_adapter.get_user_by_email(user_name, auth.tenant_id)
            if conflict is not None:
                return scim_error(
                    409, f"userName 已存在: {user_name}", scim_type="uniqueness"
                )
            return scim_error(
                400,
                "当前存储层不支持变更 userName(email)。请删除后重建用户。",
                scim_type="mutability",
            )

        try:
            metadata = dict(record.metadata or {})
            metadata["scim"] = scim_meta
            updated = await user_adapter.update_user(
                user_id,
                full_name=full_name,
                is_active=active,
                metadata=metadata,
            )
        except SSOStorageError as exc:
            logger.error("SCIM replace 存储错误: %s", exc)
            return scim_error(503, f"用户存储不可用: {exc}")

        fresh = await user_adapter.get_user_by_id(user_id) or updated or record
        logger.info("SCIM: 全量更新用户 %s (tenant=%s)", user_id, auth.tenant_id)
        return scim_json(record_to_scim_user(fresh, request))

    # PATCH 允许修改的属性路径
    _PATCHABLE_PATHS = {
        "active", "username", "externalid",
        "name.formatted", "name.givenname", "name.familyname", "emails",
    }

    @router.patch("/Users/{user_id}")
    async def patch_user(user_id: str, request: Request) -> JSONResponse:
        auth = await _auth(request)
        if isinstance(auth, JSONResponse):
            return auth

        record = await _get_tenant_user(user_id, auth.tenant_id)
        if record is None:
            return scim_error(404, f"User 不存在: {user_id}")

        try:
            payload = await request.json()
        except Exception:
            return scim_error(400, "请求体必须是合法 JSON。")
        schemas = payload.get("schemas") or []
        if SCIM_PATCH_SCHEMA not in schemas:
            return scim_error(400, f"schemas 必须包含 {SCIM_PATCH_SCHEMA}。")
        operations = payload.get("Operations")
        if not isinstance(operations, list) or not operations:
            return scim_error(400, "Operations 必须是非空数组。", scim_type="invalidSyntax")

        # 规范化: 展开无 path 的 add/replace (value 为属性字典) 为逐属性 op
        normalized: List[Dict[str, Any]] = []
        for op in operations:
            if not isinstance(op, dict):
                return scim_error(400, "每个 Operation 必须是对象。", scim_type="invalidSyntax")
            op_name = str(op.get("op") or "").lower()
            if op_name not in {"add", "replace", "remove"}:
                return scim_error(
                    400, f"不支持的 op: {op.get('op')!r} (支持 add/replace/remove)。",
                    scim_type="invalidValue",
                )
            if op.get("path") is None:
                if op_name == "remove" or not isinstance(op.get("value"), dict):
                    return scim_error(
                        400, "无 path 的 add/replace 需要对象类型 value。",
                        scim_type="invalidPath",
                    )
                for key, val in op["value"].items():
                    normalized.append({"op": op_name, "path": key, "value": val})
            else:
                normalized.append(op)

        # 工作副本
        metadata = dict(record.metadata or {})
        scim_meta = dict(metadata.get("scim") or {})
        name = dict(scim_meta.get("name") or {})
        updates: Dict[str, Any] = {}
        new_active: Optional[bool] = None

        for op in normalized:
            op_name = str(op.get("op") or "").lower()
            path = op.get("path")
            value = op.get("value")
            norm_path = str(path).strip().lower()
            if norm_path not in _PATCHABLE_PATHS:
                return scim_error(
                    400, f"不支持的 path: {path!r} (支持: {sorted(_PATCHABLE_PATHS)})。",
                    scim_type="invalidPath",
                )

            if op_name == "remove":
                if norm_path == "active":
                    new_active = False  # remove active → 停用
                elif norm_path == "externalid":
                    scim_meta["externalId"] = None
                elif norm_path.startswith("name."):
                    name.pop(norm_path.split(".", 1)[1], None)
                elif norm_path == "emails":
                    scim_meta["emails"] = None
                elif norm_path == "username":
                    return scim_error(
                        400, "userName 不可移除 (必填属性)。", scim_type="mutability"
                    )
                continue

            # add / replace
            if norm_path == "active":
                if not isinstance(value, bool):
                    return scim_error(400, "active 必须是布尔值。", scim_type="invalidValue")
                new_active = value
            elif norm_path == "username":
                new_name = str(value or "").strip()
                if not new_name:
                    return scim_error(400, "userName 不能为空。", scim_type="invalidValue")
                if new_name.lower() != record.email.lower():
                    return scim_error(
                        400,
                        "当前存储层不支持通过 PATCH 变更 userName(email)。",
                        scim_type="mutability",
                    )
            elif norm_path == "externalid":
                scim_meta["externalId"] = value
            elif norm_path == "name.formatted":
                name["formatted"] = value
            elif norm_path == "name.givenname":
                name["givenName"] = value
            elif norm_path == "name.familyname":
                name["familyName"] = value
            elif norm_path == "emails":
                if not isinstance(value, list):
                    return scim_error(400, "emails 必须是数组。", scim_type="invalidValue")
                scim_meta["emails"] = value

        # 应用工作副本
        scim_meta["name"] = name
        metadata["scim"] = scim_meta
        updates["metadata"] = metadata
        full_name = name.get("formatted") or " ".join(
            part for part in [name.get("givenName"), name.get("familyName")] if part
        ) or None
        updates["full_name"] = full_name

        try:
            await user_adapter.update_user(user_id, **updates)
            if new_active is not None:
                if new_active:
                    await user_adapter.activate_user(user_id)
                else:
                    await user_adapter.deactivate_user(user_id)
        except SSOStorageError as exc:
            logger.error("SCIM patch 存储错误: %s", exc)
            return scim_error(503, f"用户存储不可用: {exc}")

        fresh = await user_adapter.get_user_by_id(user_id) or record
        logger.info("SCIM: PATCH 用户 %s (tenant=%s)", user_id, auth.tenant_id)
        return scim_json(record_to_scim_user(fresh, request))

    @router.delete("/Users/{user_id}", status_code=204)
    async def delete_user(user_id: str, request: Request) -> JSONResponse:
        """DELETE → 软停用 (is_active=False)。

        企业 IdP 生命周期惯例: 账户保留用于审计, 停用后无法登录;
        物理删除由后续数据治理流程负责。
        """
        auth = await _auth(request)
        if isinstance(auth, JSONResponse):
            return auth

        record = await _get_tenant_user(user_id, auth.tenant_id)
        if record is None:
            return scim_error(404, f"User 不存在: {user_id}")

        try:
            await user_adapter.deactivate_user(user_id)
        except SSOStorageError as exc:
            logger.error("SCIM delete 存储错误: %s", exc)
            return scim_error(503, f"用户存储不可用: {exc}")
        logger.info("SCIM: 停用用户 %s (tenant=%s)", user_id, auth.tenant_id)
        return JSONResponse(status_code=204, content=None, media_type=SCIM_CONTENT_TYPE)

    # ------------------------------------------------------------- 发现端点

    @router.get("/ServiceProviderConfig")
    async def service_provider_config(request: Request) -> JSONResponse:
        """服务提供方能力声明 (按真实实现声明, 不夸大)。"""
        return scim_json(
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
                "documentationUri": "https://www.rfc-editor.org/rfc/rfc7644",
                "patch": {"supported": True},
                "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
                "filter": {"supported": True, "maxResults": 500},
                "changePassword": {"supported": False},
                "sort": {"supported": False},
                "etag": {"supported": False},
                "authenticationSchemes": [
                    {
                        "type": "oauthbearertoken",
                        "name": "Bearer Token (tenant-bound)",
                        "description": "SCIM bearer 令牌, 每令牌绑定一个租户。",
                        "specUri": "https://www.rfc-editor.org/rfc/rfc6750",
                        "primary": True,
                    }
                ],
            }
        )

    @router.get("/ResourceTypes")
    async def list_resource_types(request: Request) -> JSONResponse:
        base = str(request.base_url).rstrip("/")
        resource = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
            "id": "User",
            "name": "User",
            "endpoint": "/Users",
            "description": "用户账号 (租户隔离)。",
            "schema": SCIM_USER_SCHEMA,
            "meta": {
                "resourceType": "ResourceType",
                "location": f"{base}/scim/v2/ResourceTypes/User",
            },
        }
        return scim_json(
            {
                "schemas": [SCIM_LIST_SCHEMA],
                "totalResults": 1,
                "itemsPerPage": 1,
                "startIndex": 1,
                "Resources": [resource],
            }
        )

    @router.get("/ResourceTypes/User")
    async def get_resource_type(request: Request) -> JSONResponse:
        base = str(request.base_url).rstrip("/")
        return scim_json(
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
                "id": "User",
                "name": "User",
                "endpoint": "/Users",
                "description": "用户账号 (租户隔离)。",
                "schema": SCIM_USER_SCHEMA,
                "meta": {
                    "resourceType": "ResourceType",
                    "location": f"{base}/scim/v2/ResourceTypes/User",
                },
            }
        )

    _USER_SCHEMA_DOC: Dict[str, Any] = {
        "id": SCIM_USER_SCHEMA,
        "name": "User",
        "description": "用户账号",
        "attributes": [
            {
                "name": "userName",
                "type": "string",
                "multiValued": False,
                "description": "登录名 (映射到平台 email 字段)",
                "required": True,
                "caseExact": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "server",
            },
            {
                "name": "name",
                "type": "complex",
                "multiValued": False,
                "required": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
                "subAttributes": [
                    {"name": "formatted", "type": "string", "multiValued": False,
                     "required": False, "mutability": "readWrite",
                     "returned": "default", "uniqueness": "none"},
                    {"name": "givenName", "type": "string", "multiValued": False,
                     "required": False, "mutability": "readWrite",
                     "returned": "default", "uniqueness": "none"},
                    {"name": "familyName", "type": "string", "multiValued": False,
                     "required": False, "mutability": "readWrite",
                     "returned": "default", "uniqueness": "none"},
                ],
            },
            {
                "name": "emails",
                "type": "complex",
                "multiValued": True,
                "required": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
                "subAttributes": [
                    {"name": "value", "type": "string", "multiValued": False,
                     "required": True, "mutability": "readWrite",
                     "returned": "default", "uniqueness": "none"},
                    {"name": "type", "type": "string", "multiValued": False,
                     "required": False, "mutability": "readWrite",
                     "returned": "default", "uniqueness": "none"},
                    {"name": "primary", "type": "boolean", "multiValued": False,
                     "required": False, "mutability": "readWrite",
                     "returned": "default", "uniqueness": "none"},
                ],
            },
            {
                "name": "active",
                "type": "boolean",
                "multiValued": False,
                "description": "账户启用状态 (DELETE 等效于置为 false)",
                "required": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
            },
            {
                "name": "externalId",
                "type": "string",
                "multiValued": False,
                "required": False,
                "caseExact": True,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
            },
        ],
    }

    @router.get("/Schemas")
    async def list_schemas(request: Request) -> JSONResponse:
        base = str(request.base_url).rstrip("/")
        schema_doc = dict(_USER_SCHEMA_DOC)
        schema_doc["schemas"] = ["urn:ietf:params:scim:schemas:core:2.0:Schema"]
        schema_doc["meta"] = {
            "resourceType": "Schema",
            "location": f"{base}/scim/v2/Schemas/{SCIM_USER_SCHEMA}",
        }
        return scim_json(
            {
                "schemas": [SCIM_LIST_SCHEMA],
                "totalResults": 1,
                "itemsPerPage": 1,
                "startIndex": 1,
                "Resources": [schema_doc],
            }
        )

    @router.get("/Schemas/{schema_urn:path}")
    async def get_schema(schema_urn: str, request: Request) -> JSONResponse:
        if schema_urn != SCIM_USER_SCHEMA:
            return scim_error(404, f"Schema 不存在: {schema_urn}")
        base = str(request.base_url).rstrip("/")
        schema_doc = dict(_USER_SCHEMA_DOC)
        schema_doc["schemas"] = ["urn:ietf:params:scim:schemas:core:2.0:Schema"]
        schema_doc["meta"] = {
            "resourceType": "Schema",
            "location": f"{base}/scim/v2/Schemas/{SCIM_USER_SCHEMA}",
        }
        return scim_json(schema_doc)

    return router


# ============================================================================
# 默认 router (集成波挂载入口)
# ============================================================================

router = build_scim_router()


# ============================================================================
# 集成波接线说明
# ============================================================================
# 在 backend/app/main.py 中:
#   from backend.app.api.scim import router as scim_router
#   app.include_router(scim_router)
# 即挂载 /scim/v2/*。
# 生产令牌配置: 环境变量 XAGENT_SCIM_TOKENS (JSON), 例如:
#   {"<random-token-1>": {"tenant_id": "tenant-a", "description": "Okta provisioning"}}
# 测试/自定义存储: 用 build_scim_router(adapter=..., registry=...) 自建 router。
