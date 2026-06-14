"""Webhook Management API for X-Agent.

Provides CRUD endpoints for managing incoming and outgoing webhooks:
- GitHub → X-Agent (issues, PRs, pushes, etc.)
- Slack → X-Agent (messages, commands, reactions)
- X-Agent → External Services (notifications, results, logs)

Features:
- Webhook creation, update, deletion, listing
- Event filtering and subscriptions
- Webhook testing with test payloads
- Signature verification (HMAC-SHA256)
- Retry logic with exponential backoff
- Event delivery history tracking
"""

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field, HttpUrl, validator
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class WebhookDirection(str, Enum):
    """Webhook direction."""
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class WebhookEventType(str, Enum):
    """Supported webhook event types."""
    # GitHub events
    GITHUB_PUSH = "github.push"
    GITHUB_PULL_REQUEST = "github.pull_request"
    GITHUB_ISSUES = "github.issues"
    GITHUB_RELEASE = "github.release"

    # Slack events
    SLACK_MESSAGE = "slack.message"
    SLACK_COMMAND = "slack.command"
    SLACK_REACTION = "slack.reaction"

    # X-Agent internal events
    XAGENT_RUN_COMPLETED = "xagent.run.completed"
    XAGENT_RUN_FAILED = "xagent.run.failed"
    XAGENT_WORKFLOW_EXECUTED = "xagent.workflow.executed"
    XAGENT_ERROR = "xagent.error"


class WebhookConfig(BaseModel):
    """Webhook configuration."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    url: HttpUrl
    secret: Optional[str] = Field(None, description="HMAC secret for signature verification")
    events: List[WebhookEventType]
    active: bool = True
    direction: WebhookDirection = WebhookDirection.INCOMING
    retry_policy: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"max_retries": 3, "backoff_multiplier": 2},
        description="Retry configuration for outgoing webhooks"
    )
    headers: Optional[Dict[str, str]] = Field(None, description="Custom headers to include")
    
    @validator("secret")
    def validate_secret(cls, v):
        if v is not None and len(v) < 8:
            raise ValueError("Secret must be at least 8 characters")
        return v


class WebhookResponse(WebhookConfig):
    """Webhook response with ID and metadata."""
    id: str
    created_at: datetime
    updated_at: datetime
    last_triggered_at: Optional[datetime] = None
    delivery_success_count: int = 0
    delivery_failure_count: int = 0


class WebhookDeliveryLog(BaseModel):
    """Record of a webhook delivery attempt."""
    id: str
    webhook_id: str
    event_type: WebhookEventType
    request_body: Dict[str, Any]
    response_status: int
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime
    retry_count: int = 0


class WebhookTestPayload(BaseModel):
    """Test payload for webhook."""
    event_type: WebhookEventType = WebhookEventType.GITHUB_PUSH
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "action": "opened",
        "repository": {"name": "test-repo", "url": "https://github.com/test/test-repo"},
        "sender": {"login": "test-user"}
    })


# In-memory storage (in production, use database)
_webhooks: Dict[str, Dict[str, Any]] = {}
_delivery_logs: List[WebhookDeliveryLog] = []

# Lock for thread-safe operations
_lock = asyncio.Lock()


def _generate_signature(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload.
    
    Args:
        payload: JSON string of webhook payload
        secret: Shared secret
        
    Returns:
        Signature string (sha256=<hex>)
    """
    signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"


def _verify_signature(payload: str, secret: str, signature: str) -> bool:
    """Verify webhook signature.
    
    Args:
        payload: JSON string of webhook payload
        secret: Shared secret
        signature: Signature to verify (sha256=<hex>)
        
    Returns:
        True if signature is valid
    """
    expected_signature = _generate_signature(payload, secret)
    return hmac.compare_digest(expected_signature, signature)


@router.get("/", response_model=List[WebhookResponse])
async def list_webhooks(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    active_only: bool = Query(False),
    direction: Optional[WebhookDirection] = Query(None),
) -> List[WebhookResponse]:
    """List all webhooks with pagination.
    
    Args:
        skip: Number of webhooks to skip
        limit: Maximum number of webhooks to return
        active_only: Only return active webhooks
        direction: Filter by direction (incoming/outgoing)
        
    Returns:
        List of webhook configurations
    """
    async with _lock:
        webhooks = list(_webhooks.values())

    if active_only:
        webhooks = [w for w in webhooks if w["active"]]

    if direction:
        webhooks = [w for w in webhooks if w["direction"] == direction]

    # Sort by creation time (newest first)
    webhooks.sort(key=lambda w: w["created_at"], reverse=True)

    # Apply pagination
    webhooks = webhooks[skip : skip + limit]

    return [WebhookResponse(**w) for w in webhooks]


@router.post("/", response_model=WebhookResponse, status_code=201)
async def create_webhook(config: WebhookConfig) -> WebhookResponse:
    """Create a new webhook.
    
    Args:
        config: Webhook configuration
        
    Returns:
        Created webhook with ID
    """
    webhook_id = str(uuid.uuid4())
    now = datetime.utcnow()

    webhook_data = {
        "id": webhook_id,
        **config.dict(),
        "created_at": now,
        "updated_at": now,
        "last_triggered_at": None,
        "delivery_success_count": 0,
        "delivery_failure_count": 0,
    }

    async with _lock:
        _webhooks[webhook_id] = webhook_data

    logger.info(f"Created webhook {webhook_id}: {config.name}")
    return WebhookResponse(**webhook_data)


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(webhook_id: str) -> WebhookResponse:
    """Get webhook by ID.
    
    Args:
        webhook_id: Webhook ID
        
    Returns:
        Webhook configuration
        
    Raises:
        HTTPException: If webhook not found
    """
    async with _lock:
        webhook = _webhooks.get(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse(**webhook)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(webhook_id: str, config: WebhookConfig) -> WebhookResponse:
    """Update webhook configuration.
    
    Args:
        webhook_id: Webhook ID
        config: Updated configuration
        
    Returns:
        Updated webhook
        
    Raises:
        HTTPException: If webhook not found
    """
    async with _lock:
        webhook = _webhooks.get(webhook_id)
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        webhook.update(config.dict(exclude_unset=True))
        webhook["updated_at"] = datetime.utcnow()

    logger.info(f"Updated webhook {webhook_id}")
    return WebhookResponse(**webhook)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: str):
    """Delete webhook.
    
    Args:
        webhook_id: Webhook ID
        
    Raises:
        HTTPException: If webhook not found
    """
    async with _lock:
        if webhook_id not in _webhooks:
            raise HTTPException(status_code=404, detail="Webhook not found")
        del _webhooks[webhook_id]

    logger.info(f"Deleted webhook {webhook_id}")


@router.post("/{webhook_id}/test", status_code=200)
async def test_webhook(
    webhook_id: str,
    payload: Optional[WebhookTestPayload] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Dict[str, Any]:
    """Test webhook delivery with sample payload.
    
    Args:
        webhook_id: Webhook ID
        payload: Test payload (optional, uses default if not provided)
        background_tasks: Background task runner
        
    Returns:
        Test result with HTTP status and response
        
    Raises:
        HTTPException: If webhook not found
    """
    async with _lock:
        webhook = _webhooks.get(webhook_id)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if not payload:
        payload = WebhookTestPayload()

    # Execute test in background
    background_tasks.add_task(
        _send_webhook_delivery,
        webhook=webhook,
        event_type=payload.event_type,
        payload=payload.payload,
    )

    return {
        "webhook_id": webhook_id,
        "test_initiated": True,
        "message": "Test delivery initiated. Check webhook logs for details.",
    }


@router.get("/{webhook_id}/deliveries")
async def get_delivery_history(
    webhook_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    success_only: bool = Query(False),
) -> Dict[str, Any]:
    """Get webhook delivery history.
    
    Args:
        webhook_id: Webhook ID
        skip: Number of logs to skip
        limit: Maximum logs to return
        success_only: Only return successful deliveries
        
    Returns:
        Delivery logs with pagination info
    """
    async with _lock:
        if webhook_id not in _webhooks:
            raise HTTPException(status_code=404, detail="Webhook not found")

        logs = [log for log in _delivery_logs if log.webhook_id == webhook_id]

    if success_only:
        logs = [log for log in logs if log.response_status == 200]

    # Sort by timestamp (newest first)
    logs.sort(key=lambda l: l.timestamp, reverse=True)

    total = len(logs)
    logs = logs[skip : skip + limit]

    return {
        "webhook_id": webhook_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "deliveries": logs,
    }


@router.get("/{webhook_id}/stats")
async def get_webhook_stats(webhook_id: str) -> Dict[str, Any]:
    """Get webhook statistics.
    
    Args:
        webhook_id: Webhook ID
        
    Returns:
        Statistics including delivery success/failure rates
    """
    async with _lock:
        webhook = _webhooks.get(webhook_id)
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        logs = [log for log in _delivery_logs if log.webhook_id == webhook_id]

    successful = sum(1 for log in logs if log.response_status == 200)
    failed = sum(1 for log in logs if log.response_status >= 400)
    total = len(logs)

    return {
        "webhook_id": webhook_id,
        "total_deliveries": total,
        "successful": successful,
        "failed": failed,
        "success_rate": (successful / total * 100) if total > 0 else 0,
        "last_triggered": webhook.get("last_triggered_at"),
        "events_subscribed": webhook.get("events", []),
    }


async def _send_webhook_delivery(
    webhook: Dict[str, Any],
    event_type: WebhookEventType,
    payload: Dict[str, Any],
    retry_count: int = 0,
):
    """Send webhook delivery with retry logic.
    
    Args:
        webhook: Webhook configuration
        event_type: Event type being delivered
        payload: Payload to send
        retry_count: Current retry attempt
    """
    import aiohttp

    payload_json = json.dumps(payload)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "X-Agent/1.0",
        "X-Event-Type": event_type.value,
    }

    # Add custom headers from webhook config
    if webhook.get("headers"):
        headers.update(webhook["headers"])

    # Add signature if secret is configured
    if webhook.get("secret"):
        signature = _generate_signature(payload_json, webhook["secret"])
        headers["X-Webhook-Signature"] = signature

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                str(webhook["url"]),
                data=payload_json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                response_body = await resp.text()

                # Log delivery attempt
                log_entry = WebhookDeliveryLog(
                    id=str(uuid.uuid4()),
                    webhook_id=webhook["id"],
                    event_type=event_type,
                    request_body=payload,
                    response_status=resp.status,
                    response_body=response_body[:500] if response_body else None,
                    error_message=None,
                    timestamp=datetime.utcnow(),
                    retry_count=retry_count,
                )

                async with _lock:
                    _delivery_logs.append(log_entry)

                    # Update webhook stats
                    webhook_data = _webhooks.get(webhook["id"])
                    if webhook_data:
                        webhook_data["last_triggered_at"] = datetime.utcnow()
                        if resp.status == 200:
                            webhook_data["delivery_success_count"] += 1
                        else:
                            webhook_data["delivery_failure_count"] += 1

                logger.info(
                    f"Webhook {webhook['id']} delivery: "
                    f"status={resp.status}, retry={retry_count}"
                )

                # Retry logic for non-2xx responses
                if resp.status >= 500 and retry_count < webhook.get("retry_policy", {}).get("max_retries", 3):
                    backoff = (
                        webhook.get("retry_policy", {}).get("backoff_multiplier", 2) ** retry_count
                    )
                    await asyncio.sleep(backoff)
                    await _send_webhook_delivery(webhook, event_type, payload, retry_count + 1)

    except Exception as e:
        logger.error(f"Webhook {webhook['id']} delivery failed: {str(e)}")

        # Log error
        log_entry = WebhookDeliveryLog(
            id=str(uuid.uuid4()),
            webhook_id=webhook["id"],
            event_type=event_type,
            request_body=payload,
            response_status=0,
            response_body=None,
            error_message=str(e),
            timestamp=datetime.utcnow(),
            retry_count=retry_count,
        )

        async with _lock:
            _delivery_logs.append(log_entry)
            webhook_data = _webhooks.get(webhook["id"])
            if webhook_data:
                webhook_data["delivery_failure_count"] += 1

        # Retry on network errors
        if retry_count < webhook.get("retry_policy", {}).get("max_retries", 3):
            backoff = (
                webhook.get("retry_policy", {}).get("backoff_multiplier", 2) ** retry_count
            )
            await asyncio.sleep(backoff)
            await _send_webhook_delivery(webhook, event_type, payload, retry_count + 1)


# Helper function to trigger webhooks from other parts of the application
async def trigger_webhook(event_type: WebhookEventType, payload: Dict[str, Any]):
    """Trigger outgoing webhooks for an event.
    
    This is called by other parts of X-Agent to notify subscribed external services.
    
    Args:
        event_type: Type of event
        payload: Event payload
    """
    async with _lock:
        relevant_webhooks = [
            w for w in _webhooks.values()
            if w["active"]
            and w["direction"] == WebhookDirection.OUTGOING
            and event_type in [WebhookEventType(e) for e in w.get("events", [])]
        ]

    for webhook in relevant_webhooks:
        asyncio.create_task(
            _send_webhook_delivery(webhook, event_type, payload)
        )
