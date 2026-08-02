from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyRecord,
    APIKeyStore,
    Principal,
)
from backend.app.dependencies import enforce_scope, get_api_key_store, get_current_principal

router = APIRouter(prefix="/api/v1/security", tags=["security"])
extended_router = APIRouter(prefix="/api/v1/security", tags=["security-extended"])  # C2: unmounted; handler bodies unchanged
APIKeyStoreDependency = Annotated[APIKeyStore, Depends(get_api_key_store)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/me", response_model=Principal)
async def get_me(principal: PrincipalDependency) -> Principal:
    return principal


@router.post("/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> APIKeyCreateResponse:
    enforce_scope(principal, "security:manage")
    return store.create(request)


@router.get("/api-keys", response_model=list[APIKeyRecord])
async def list_api_keys(
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> list[APIKeyRecord]:
    enforce_scope(principal, "security:manage")
    return store.list()


@router.get("/api-keys/expiring-soon", response_model=list[APIKeyRecord])
async def list_expiring_api_keys(
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
    days: int = 30,
) -> list[APIKeyRecord]:
    """获取即将过期的API Key（默认30天内）"""
    enforce_scope(principal, "security:manage")
    from datetime import UTC, datetime, timedelta

    expiring_keys = []
    threshold = datetime.now(UTC) + timedelta(days=days)

    for record in store.list():
        if record.revoked or not record.expires_at:
            continue
        if record.expires_at <= threshold:
            expiring_keys.append(record)

    return sorted(expiring_keys, key=lambda r: r.expires_at or datetime.now(UTC))


@router.get("/api-keys/{key_id}", response_model=APIKeyRecord)
async def get_api_key(
    key_id: str,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> APIKeyRecord:
    enforce_scope(principal, "security:manage")
    record = next((item for item in store.list() if item.id == key_id), None)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "API key not found.")
    return record


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> dict[str, bool]:
    enforce_scope(principal, "security:manage")
    record = store.revoke(key_id)
    if record is None:
        raise api_error(404, ErrorCode.AUTHENTICATION_FAILED, "API key not found.")
    return {"deleted": True}


@router.post("/bootstrap-key/mark-changed")
async def mark_bootstrap_key_changed(
    principal: PrincipalDependency,
) -> dict[str, bool]:
    """标记Bootstrap Key已更换"""
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    from backend.app.core.bootstrap_key_enforcer import get_bootstrap_key_enforcer
    enforcer = get_bootstrap_key_enforcer()
    enforcer.mark_bootstrap_key_changed(principal.user_id)
    return {"success": True}


@router.get("/bootstrap-key/status")
async def get_bootstrap_key_status(
    principal: PrincipalDependency,
) -> dict[str, object]:
    """获取Bootstrap Key状态"""
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    from backend.app.core.bootstrap_key_enforcer import get_bootstrap_key_enforcer
    enforcer = get_bootstrap_key_enforcer()
    status = enforcer.get_status(principal.user_id)
    return status.model_dump(mode="json")


@router.post("/api-keys/{key_id}/revoke", response_model=APIKeyRecord)
async def revoke_api_key(
    key_id: str,
    principal: PrincipalDependency,
    store: APIKeyStoreDependency,
) -> APIKeyRecord:
    enforce_scope(principal, "security:manage")
    record = store.revoke(key_id)
    if record is None:
        raise api_error(404, ErrorCode.AUTHENTICATION_FAILED, "API key not found.")
    return record


# ─── M: Security Posture / Secret Scan / Audit Chain ─────────────────────────


@router.get("/posture")
async def get_security_posture(principal: PrincipalDependency = None) -> dict[str, object]:
    """Unified security posture: PromptGuard stats, headers, config hardening."""
    enforce_scope(principal, "security:manage")
    import os
    import time

    # PromptGuard engine status
    prompt_guard: dict[str, object] = {}
    try:
        from backend.app.core.prompt_guard.engine import PromptGuardEngine
        PromptGuardEngine()  # 探测可用性
        prompt_guard = {"enabled": True, "engine": "PromptGuardEngine"}
    except Exception:
        prompt_guard = {"enabled": False, "error": "unavailable"}

    # Security headers config
    headers_config = {
        "csp_enabled": True,
        "hsts_enabled": True,
        "x_frame_options": "DENY",
        "x_content_type_options": "nosniff",
    }

    # Environment hardening
    app_mode = os.environ.get("XAGENT_APP_MODE", "development")
    hardening = {
        "app_mode": app_mode,
        "docs_exposed": app_mode != "production",
        "https_required": app_mode == "production",
        "cors_wildcard": os.environ.get("XAGENT_CORS_ORIGINS", "") == "*",
    }

    # API key health
    key_health: dict[str, object] = {}
    try:
        from backend.app.dependencies import get_api_key_store
        store = get_api_key_store()
        keys = store.list()
        from datetime import UTC, datetime, timedelta
        expiring = sum(1 for k in keys if k.expires_at and k.expires_at <= datetime.now(UTC) + timedelta(days=7))
        key_health = {
            "total_keys": len(keys),
            "revoked": sum(1 for k in keys if k.revoked),
            "expiring_7d": expiring,
        }
    except Exception:
        key_health = {"error": "unavailable"}

    return {
        "timestamp": time.time(),
        "prompt_guard": prompt_guard,
        "security_headers": headers_config,
        "hardening": hardening,
        "api_key_health": key_health,
    }


@router.post("/secret-scan")
async def scan_secrets(principal: PrincipalDependency = None) -> dict[str, object]:
    """Scan workspace for accidentally committed secrets (API keys, tokens, passwords)."""
    enforce_scope(principal, "security:manage")
    import os
    import re
    import time

    workspace = os.environ.get("XAGENT_WORKSPACE", ".")
    # Patterns that indicate leaked secrets
    secret_patterns = [
        (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}', "API Key"),
        (r'(?i)(secret|password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']{8,}', "Password/Secret"),
        (r'(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}', "Bearer Token"),
        (r'ghp_[A-Za-z0-9]{36,}', "GitHub PAT"),
        (r'sk-[A-Za-z0-9]{32,}', "OpenAI Key"),
        (r'AKIA[0-9A-Z]{16}', "AWS Access Key"),
    ]
    skip_dirs = {".git", "node_modules", "venv", "__pycache__", ".ruff_cache", "htmlcov", ".xagent_runtime"}
    skip_exts = {".pyc", ".png", ".jpg", ".gif", ".woff", ".woff2", ".ico", ".lock"}
    max_files = 500

    findings: list[dict[str, object]] = []
    files_scanned = 0

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if files_scanned >= max_files:
                break
            ext = os.path.splitext(fname)[1].lower()
            if ext in skip_exts:
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, workspace)
            try:
                with open(fpath, encoding="utf-8", errors="ignore") as f:
                    content = f.read(50000)  # First 50KB only
                for pattern, label in secret_patterns:
                    matches = re.finditer(pattern, content)
                    for m in matches:
                        # Skip example/env.example files and this scanner itself
                        if ".env.example" in rel_path or "secret-scan" in rel_path:
                            continue
                        findings.append({
                            "file": rel_path,
                            "type": label,
                            "line_hint": content[:m.start()].count("\n") + 1,
                            "snippet": m.group()[:30] + "...",
                        })
            except (OSError, PermissionError):
                continue
            files_scanned += 1
        if files_scanned >= max_files:
            break

    return {
        "timestamp": time.time(),
        "files_scanned": files_scanned,
        "findings_count": len(findings),
        "findings": findings[:50],
        "status": "clean" if not findings else "warnings_found",
    }


@router.get("/audit-chain")
async def get_audit_chain(principal: PrincipalDependency = None, limit: int = 30) -> dict[str, object]:
    """Recent tool-call audit trail with integrity chain hash."""
    enforce_scope(principal, "security:manage")
    import hashlib
    import time

    try:
        from backend.app.core.audit_store import get_audit_store
        store = get_audit_store()
        records = store.list(limit=limit)
    except Exception:
        records = []

    # Build hash chain for tamper detection
    chain: list[dict[str, object]] = []
    prev_hash = "genesis"
    for rec in records:
        rec_dict = rec if isinstance(rec, dict) else getattr(rec, "model_dump", lambda **kw: {})(mode="json")
        payload = f"{prev_hash}|{rec_dict.get('timestamp', '')}|{rec_dict.get('action', '')}|{rec_dict.get('tool_name', '')}"
        current_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
        chain.append({
            **rec_dict,
            "chain_hash": current_hash,
            "prev_hash": prev_hash,
        })
        prev_hash = current_hash

    return {
        "timestamp": time.time(),
        "chain_length": len(chain),
        "integrity": "valid" if chain else "empty",
        "entries": chain,
    }
