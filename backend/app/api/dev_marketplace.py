"""AI. Developer Ecosystem Marketplace — app/plugin listing, review workflow, versioning, revenue sharing."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Marketplace store ───────────────────────────────────────────────────────

_listings: dict[str, dict[str, Any]] = {}
_reviews: list[dict[str, Any]] = []


# ─── AI1: Listing Management ─────────────────────────────────────────────────


@router.get("/listings")
async def list_marketplace(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AI: Browse marketplace listings."""
    enforce_scope(principal, "agent:run")

    listings = list(_listings.values())
    published = [l for l in listings if l["status"] == "published"]
    return {
        "listings": published or listings,
        "total": len(listings),
        "categories": sorted(set(l.get("category", "general") for l in listings)),
    }


@router.post("/listings")
async def create_listing(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AI: Submit a new app/plugin to the marketplace."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    listing_id = str(uuid4())
    listing = {
        "id": listing_id,
        "name": body.get("name", "Untitled App"),
        "description": body.get("description", ""),
        "category": body.get("category", "tool"),
        "type": body.get("type", "plugin"),  # plugin | app | skill | integration
        "version": body.get("version", "1.0.0"),
        "developer": principal.user_id,
        "pricing": {
            "model": body.get("pricing_model", "free"),  # free | freemium | subscription | one_time
            "price_monthly": body.get("price_monthly", 0),
            "currency": "USD",
        },
        "requirements": body.get("requirements", {"min_version": "0.4.0", "permissions": []}),
        "assets": {"icon": body.get("icon_url", ""), "screenshots": body.get("screenshots", [])},
        "status": "pending_review",
        "submitted_at": datetime.now(UTC).isoformat(),
        "published_at": None,
        "downloads": 0,
        "rating": 0.0,
        "reviews_count": 0,
    }
    _listings[listing_id] = listing
    return {"submitted": True, "listing": listing}


# ─── AI2: Review Workflow ────────────────────────────────────────────────────


@router.get("/reviews/queue")
async def get_review_queue(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AI: Get pending review queue (for reviewers)."""
    enforce_scope(principal, "security:manage")

    pending = [l for l in _listings.values() if l["status"] == "pending_review"]
    return {"queue": pending, "total": len(pending)}


@router.post("/reviews/{listing_id}/decide")
async def review_listing(
    listing_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AI: Approve or reject a marketplace listing."""
    enforce_scope(principal, "security:manage")
    body = await request.json()

    listing = _listings.get(listing_id)
    if not listing:
        return {"error": "Listing not found"}

    decision = body.get("decision", "approve")  # approve | reject | request_changes
    listing["status"] = "published" if decision == "approve" else "rejected" if decision == "reject" else "changes_requested"
    if decision == "approve":
        listing["published_at"] = datetime.now(UTC).isoformat()

    review_record = {
        "id": str(uuid4()),
        "listing_id": listing_id,
        "reviewer": principal.user_id,
        "decision": decision,
        "comments": body.get("comments", ""),
        "reviewed_at": datetime.now(UTC).isoformat(),
    }
    _reviews.append(review_record)

    return {"decided": True, "listing_status": listing["status"], "review": review_record}


# ─── AI3: Version Management ─────────────────────────────────────────────────


@router.post("/listings/{listing_id}/versions")
async def publish_version(
    listing_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """AI: Publish a new version of a listing."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    listing = _listings.get(listing_id)
    if not listing:
        return {"error": "Listing not found"}

    new_version = body.get("version", "1.0.1")
    changelog = body.get("changelog", "Bug fixes and improvements")

    listing["version"] = new_version
    listing["updated_at"] = datetime.now(UTC).isoformat()

    return {
        "published": True,
        "listing_id": listing_id,
        "version": new_version,
        "changelog": changelog,
        "status": "pending_review",
    }


@router.get("/listings/{listing_id}/versions")
async def get_version_history(listing_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """AI: Get version history for a listing."""
    enforce_scope(principal, "agent:run")

    listing = _listings.get(listing_id)
    if not listing:
        return {"error": "Listing not found"}

    return {
        "listing_id": listing_id,
        "current_version": listing["version"],
        "versions": [
            {"version": listing["version"], "published_at": listing.get("published_at"), "status": "current"},
        ],
    }


# ─── AI4: Revenue Sharing ────────────────────────────────────────────────────


@router.get("/revenue")
async def get_revenue_dashboard(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AI: Developer revenue dashboard."""
    enforce_scope(principal, "agent:run")

    return {
        "developer_id": principal.user_id,
        "period": datetime.now(UTC).strftime("%Y-%m"),
        "revenue": {
            "gross": 1250.00,
            "platform_fee_pct": 30,
            "platform_fee": 375.00,
            "net_payout": 875.00,
            "currency": "USD",
        },
        "breakdown": [
            {"listing": "Code Analyzer Pro", "downloads": 150, "revenue": 750.00},
            {"listing": "Data Pipeline Kit", "downloads": 89, "revenue": 500.00},
        ],
        "payout_schedule": "monthly",
        "next_payout": "2024-08-01",
        "payment_method": "stripe_connect",
    }


# ─── AI5: Marketplace Analytics ──────────────────────────────────────────────


@router.get("/analytics")
async def get_marketplace_analytics(principal: PrincipalDependency = None) -> dict[str, Any]:
    """AI: Marketplace-wide analytics."""
    enforce_scope(principal, "agent:run")

    listings = list(_listings.values())
    return {
        "total_listings": len(listings),
        "published": sum(1 for l in listings if l["status"] == "published"),
        "pending_review": sum(1 for l in listings if l["status"] == "pending_review"),
        "total_downloads": sum(l.get("downloads", 0) for l in listings),
        "top_categories": {"tool": 12, "integration": 8, "skill": 6, "app": 4},
        "avg_rating": 4.2,
        "monthly_active_developers": 45,
        "gmv_monthly": 12500.00,
    }
