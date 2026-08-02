"""AD. White-Label & Multi-Brand Customization — theme engine, domain isolation, brand asset injection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/branding", tags=["branding"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Brand store ─────────────────────────────────────────────────────────────

_brands: dict[str, dict[str, Any]] = {
    "default": {
        "id": "default",
        "name": "X-Agent",
        "domain": "app.xagent.ai",
        "theme": {
            "primary_color": "#3B82F6",
            "secondary_color": "#10B981",
            "background": "#FFFFFF",
            "surface": "#F9FAFB",
            "text_primary": "#111827",
            "text_secondary": "#6B7280",
            "border_radius": "8px",
            "font_family": "Inter, system-ui, sans-serif",
            "logo_url": "/assets/logo-default.svg",
            "favicon_url": "/assets/favicon-default.ico",
        },
        "customization": {
            "app_title": "X-Agent Console",
            "welcome_message": "Welcome to X-Agent",
            "support_email": "support@xagent.ai",
            "footer_text": "© 2024 X-Agent. All rights reserved.",
            "custom_css": "",
            "custom_js": "",
            "login_background": "",
            "hide_powered_by": False,
        },
        "features": {
            "custom_domain": False,
            "sso_enabled": False,
            "custom_roles": False,
            "audit_export": True,
            "api_whitelabel": False,
        },
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z",
    },
}


# ─── AD1: Brand Configuration ────────────────────────────────────────────────


@router.get("/brands")
async def list_brands(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AD: List all brand configurations."""
    enforce_scope(principal, "agent:run")

    return {
        "brands": list(_brands.values()),
        "total": len(_brands),
        "active": sum(1 for b in _brands.values() if b["status"] == "active"),
    }


@router.post("/brands")
async def create_brand(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AD: Create a new white-label brand configuration."""
    enforce_scope(principal, "security:manage")
    body = await request.json()

    brand_id = body.get("id", str(uuid4())[:8])
    brand = {
        "id": brand_id,
        "name": body.get("name", "New Brand"),
        "domain": body.get("domain", f"{brand_id}.xagent.ai"),
        "theme": {
            "primary_color": body.get("primary_color", "#3B82F6"),
            "secondary_color": body.get("secondary_color", "#10B981"),
            "background": body.get("background", "#FFFFFF"),
            "surface": body.get("surface", "#F9FAFB"),
            "text_primary": body.get("text_primary", "#111827"),
            "text_secondary": body.get("text_secondary", "#6B7280"),
            "border_radius": body.get("border_radius", "8px"),
            "font_family": body.get("font_family", "Inter, system-ui, sans-serif"),
            "logo_url": body.get("logo_url", ""),
            "favicon_url": body.get("favicon_url", ""),
        },
        "customization": {
            "app_title": body.get("app_title", body.get("name", "Console")),
            "welcome_message": body.get("welcome_message", "Welcome"),
            "support_email": body.get("support_email", ""),
            "footer_text": body.get("footer_text", ""),
            "custom_css": body.get("custom_css", ""),
            "custom_js": body.get("custom_js", ""),
            "login_background": body.get("login_background", ""),
            "hide_powered_by": body.get("hide_powered_by", False),
        },
        "features": {
            "custom_domain": body.get("custom_domain", False),
            "sso_enabled": body.get("sso_enabled", False),
            "custom_roles": body.get("custom_roles", False),
            "audit_export": body.get("audit_export", True),
            "api_whitelabel": body.get("api_whitelabel", False),
        },
        "status": "active",
        "created_at": datetime.now(UTC).isoformat(),
        "created_by": principal.user_id,
    }
    _brands[brand_id] = brand
    return {"created": True, "brand": brand}


# ─── AD2: Theme Engine ───────────────────────────────────────────────────────


@router.get("/theme/{brand_id}")
async def get_brand_theme(brand_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """AD: Get resolved theme for a brand (CSS variables format)."""
    enforce_scope(principal, "agent:run")

    brand = _brands.get(brand_id)
    if not brand:
        return {"error": f"Brand '{brand_id}' not found"}

    theme = brand["theme"]
    # Convert to CSS custom properties
    css_vars = {
        "--color-primary": theme["primary_color"],
        "--color-secondary": theme["secondary_color"],
        "--color-background": theme["background"],
        "--color-surface": theme["surface"],
        "--color-text-primary": theme["text_primary"],
        "--color-text-secondary": theme["text_secondary"],
        "--border-radius": theme["border_radius"],
        "--font-family": theme["font_family"],
    }

    return {
        "brand_id": brand_id,
        "brand_name": brand["name"],
        "css_variables": css_vars,
        "theme": theme,
        "assets": {
            "logo": theme.get("logo_url", ""),
            "favicon": theme.get("favicon_url", ""),
        },
    }


@router.put("/theme/{brand_id}")
async def update_brand_theme(
    brand_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AD: Update theme colors and assets for a brand."""
    enforce_scope(principal, "security:manage")
    body = await request.json()

    brand = _brands.get(brand_id)
    if not brand:
        return {"error": f"Brand '{brand_id}' not found"}

    # Merge theme updates
    for key, value in body.items():
        if key in brand["theme"]:
            brand["theme"][key] = value

    brand["updated_at"] = datetime.now(UTC).isoformat()
    return {"updated": True, "brand": brand}


# ─── AD3: Domain Isolation ───────────────────────────────────────────────────


@router.get("/domains")
async def list_domains(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AD: List custom domain mappings."""
    enforce_scope(principal, "agent:run")

    domains = [
        {"domain": b["domain"], "brand_id": b["id"], "brand_name": b["name"], "ssl": True, "verified": True}
        for b in _brands.values()
    ]

    return {
        "domains": domains,
        "total": len(domains),
        "wildcard_available": True,
        "ssl_provider": "lets_encrypt",
    }


@router.post("/domains/verify")
async def verify_domain(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AD: Verify domain ownership (DNS TXT record check stub)."""
    enforce_scope(principal, "security:manage")
    body = await request.json()

    domain = body.get("domain", "")
    if not domain:
        return {"error": "Domain required"}

    # In production: check DNS TXT record
    return {
        "domain": domain,
        "verified": True,
        "verification_method": "dns_txt",
        "txt_record": f"xagent-verify={uuid4().hex[:16]}",
        "ssl_status": "provisioning",
        "estimated_ssl_ready": "5 minutes",
    }


# ─── AD4: Brand Preview ──────────────────────────────────────────────────────


@router.get("/preview/{brand_id}")
async def get_brand_preview(brand_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """AD: Get full brand preview data for frontend rendering."""
    enforce_scope(principal, "agent:run")

    brand = _brands.get(brand_id)
    if not brand:
        return {"error": f"Brand '{brand_id}' not found"}

    return {
        "brand": brand,
        "preview": {
            "app_title": brand["customization"]["app_title"],
            "welcome_message": brand["customization"]["welcome_message"],
            "footer_text": brand["customization"]["footer_text"],
            "powered_by_visible": not brand["customization"]["hide_powered_by"],
            "login_page": {
                "background": brand["customization"].get("login_background", ""),
                "logo": brand["theme"].get("logo_url", ""),
                "primary_button_color": brand["theme"]["primary_color"],
            },
            "dashboard": {
                "header_color": brand["theme"]["primary_color"],
                "card_background": brand["theme"]["surface"],
                "accent_color": brand["theme"]["secondary_color"],
            },
        },
        "feature_flags": brand["features"],
    }


# ─── AD5: API White-Label Headers ────────────────────────────────────────────


@router.get("/api-config/{brand_id}")
async def get_api_whitelabel_config(brand_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """AD: Get API response white-label configuration."""
    enforce_scope(principal, "agent:run")

    brand = _brands.get(brand_id)
    if not brand:
        return {"error": f"Brand '{brand_id}' not found"}

    return {
        "brand_id": brand_id,
        "api_headers": {
            "X-App-Name": brand["customization"]["app_title"],
            "X-Brand-Domain": brand["domain"],
            "X-Support-Contact": brand["customization"].get("support_email", ""),
        },
        "response_customization": {
            "remove_xagent_references": brand["features"].get("api_whitelabel", False),
            "custom_error_messages": True,
            "custom_rate_limit_headers": True,
        },
        "sdk_config": {
            "package_name": f"@{brand_id}/sdk",
            "api_base_url": f"https://{brand['domain']}/api/v1",
            "auth_header": "X-API-Key",
        },
    }
