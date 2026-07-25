"""
X-Agent Partner SDK for Python.

A comprehensive SDK for integrating with X-Agent Partner API.

Installation (local build, not published to PyPI):
    pip install ./sdks/python        # from repository root
    # or: python -m pip wheel ./sdks/python --no-deps -w dist

Usage:
    from xagent_partner import PartnerClient

    client = PartnerClient(api_key="xag_partner_xxx")
    partner = client.get_partner("partner_id")
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)

__version__ = "0.2.0-alpha"  # 版本单一事实源: pyproject.toml 通过 [tool.setuptools.dynamic] 动态读取本值
__all__ = [
    "PartnerClient",
    "PartnerAPIError",
    "PartnerAuthError",
    "PartnerNotFoundError",
    "PartnerRateLimitError",
]


class PartnerAPIError(Exception):
    """Base exception for Partner API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[dict] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class PartnerAuthError(PartnerAPIError):
    """Authentication error."""

    pass


class PartnerNotFoundError(PartnerAPIError):
    """Resource not found error."""

    pass


class PartnerRateLimitError(PartnerAPIError):
    """Rate limit exceeded error."""

    pass


class PartnerClient:
    """
    X-Agent Partner API Client.

    Provides methods for managing partners, API keys, webhooks, and usage.

    Args:
        api_key: Partner API key
        base_url: Base URL for API (default: https://api.x-agent.io)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retries (default: 3)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.x-agent.io",
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(
            timeout=timeout,
            headers=self._get_headers(),
        )

    def _get_headers(self) -> dict[str, str]:
        """Get default request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"xagent-partner-sdk/{__version__}",
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        url = urljoin(self.base_url, endpoint)

        for attempt in range(self.max_retries):
            try:
                response = self._client.request(method, url, **kwargs)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.max_retries - 1:
                        import time

                        time.sleep(retry_after)
                        continue
                    raise PartnerRateLimitError(
                        "Rate limit exceeded",
                        status_code=429,
                        response=response.json(),
                    )

                # Handle server errors
                if response.status_code >= 500:
                    if attempt < self.max_retries - 1:
                        import time

                        wait_time = 2 ** attempt
                        time.sleep(wait_time)
                        continue

                # Handle client errors
                if response.status_code == 401:
                    error_data = response.json()
                    raise PartnerAuthError(
                        error_data.get("detail") or "Unauthorized",
                        status_code=401,
                        response=error_data,
                    )

                if response.status_code == 404:
                    error_data = response.json()
                    raise PartnerNotFoundError(
                        error_data.get("detail") or "Resource not found",
                        status_code=404,
                        response=error_data,
                    )

                if response.status_code >= 400:
                    error_data = response.json()
                    message = (
                        error_data.get("error", {}).get("message")
                        or error_data.get("detail")  # FastAPI HTTPException shape
                        or "API error"
                    )
                    if not isinstance(message, str):
                        message = str(message)
                    raise PartnerAPIError(
                        message,
                        status_code=response.status_code,
                        response=error_data,
                    )

                # No-content responses (e.g., 204 from DELETE endpoints)
                if response.status_code == 204 or not response.content:
                    return {}

                return response.json()

            except httpx.RequestError as e:
                if attempt == self.max_retries - 1:
                    raise PartnerAPIError(f"Request failed: {e}")
                import time

                time.sleep(2 ** attempt)

        raise PartnerAPIError("Max retries exceeded")

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> PartnerClient:
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    # ========================================================================
    # PARTNER MANAGEMENT
    # ========================================================================

    def register_partner(
        self,
        company_name: str,
        contact_email: str,
        contact_name: str,
        company_website: Optional[str] = None,
        description: Optional[str] = None,
        integration_type: str = "standard",
        use_cases: Optional[list[str]] = None,
        expected_volume: Optional[str] = None,
    ) -> dict[str, Any]:
        """Register a new partner."""
        payload = {
            "company_name": company_name,
            "contact_email": contact_email,
            "contact_name": contact_name,
            "company_website": company_website,
            "description": description,
            "integration_type": integration_type,
            "use_cases": use_cases or [],
            "expected_volume": expected_volume,
        }
        return self._make_request("POST", "/api/v1/partners/register", json=payload)

    def get_partner(self, partner_id: str) -> dict[str, Any]:
        """Get partner information."""
        return self._make_request("GET", f"/api/v1/partners/{partner_id}")

    def list_partners(
        self,
        status_filter: Optional[str] = None,
        integration_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List all partners."""
        params = {
            "skip": skip,
            "limit": limit,
        }
        if status_filter:
            params["status_filter"] = status_filter
        if integration_type:
            params["integration_type"] = integration_type

        response = self._make_request("GET", "/api/v1/partners", params=params)
        return response if isinstance(response, list) else response.get("partners", [])

    def update_partner(self, partner_id: str, **updates: Any) -> dict[str, Any]:
        """Update partner information."""
        return self._make_request("PATCH", f"/api/v1/partners/{partner_id}", json=updates)

    def approve_partner(self, partner_id: str) -> dict[str, Any]:
        """Approve a pending partner."""
        return self._make_request("POST", f"/api/v1/partners/{partner_id}/approve")

    def suspend_partner(self, partner_id: str, reason: str) -> dict[str, Any]:
        """Suspend a partner."""
        return self._make_request(
            "POST",
            f"/api/v1/partners/{partner_id}/suspend",
            params={"reason": reason},
        )

    # ========================================================================
    # API KEY MANAGEMENT
    # ========================================================================

    def create_api_key(
        self,
        partner_id: str,
        name: str,
        expires_in_days: int = 365,
        rate_limit_rpm: int = 1000,
        rate_limit_rph: int = 50000,
        ip_whitelist: Optional[list[str]] = None,
        scopes: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new API key for partner."""
        payload = {
            "name": name,
            "expires_in_days": expires_in_days,
            "rate_limit_rpm": rate_limit_rpm,
            "rate_limit_rph": rate_limit_rph,
            "ip_whitelist": ip_whitelist,
            "scopes": scopes or [],
        }
        return self._make_request(
            "POST",
            f"/api/v1/partners/{partner_id}/api-keys",
            json=payload,
        )

    def list_api_keys(
        self,
        partner_id: str,
        status_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List API keys for partner."""
        params = {}
        if status_filter:
            params["status_filter"] = status_filter

        response = self._make_request(
            "GET",
            f"/api/v1/partners/{partner_id}/api-keys",
            params=params,
        )
        return response if isinstance(response, list) else response.get("keys", [])

    def rotate_api_key(self, partner_id: str, key_id: str) -> dict[str, Any]:
        """Rotate an API key."""
        return self._make_request(
            "POST",
            f"/api/v1/partners/{partner_id}/api-keys/{key_id}/rotate",
        )

    def revoke_api_key(self, partner_id: str, key_id: str) -> None:
        """Revoke an API key."""
        self._make_request(
            "DELETE",
            f"/api/v1/partners/{partner_id}/api-keys/{key_id}",
        )

    # ========================================================================
    # WEBHOOK MANAGEMENT
    # ========================================================================

    def register_webhook(
        self,
        partner_id: str,
        event_type: str,
        url: str,
        active: bool = True,
        retry_policy: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Register a webhook."""
        payload = {
            "event_type": event_type,
            "url": url,
            "active": active,
            "retry_policy": retry_policy,
        }
        return self._make_request(
            "POST",
            f"/api/v1/partners/{partner_id}/webhooks",
            json=payload,
        )

    def list_webhooks(self, partner_id: str) -> list[dict[str, Any]]:
        """List webhooks for partner."""
        response = self._make_request(
            "GET",
            f"/api/v1/partners/{partner_id}/webhooks",
        )
        return response if isinstance(response, list) else response.get("webhooks", [])

    def update_webhook(
        self,
        partner_id: str,
        webhook_id: str,
        **updates: Any,
    ) -> dict[str, Any]:
        """Update webhook configuration."""
        return self._make_request(
            "PATCH",
            f"/api/v1/partners/{partner_id}/webhooks/{webhook_id}",
            json=updates,
        )

    def delete_webhook(self, partner_id: str, webhook_id: str) -> None:
        """Delete a webhook."""
        self._make_request(
            "DELETE",
            f"/api/v1/partners/{partner_id}/webhooks/{webhook_id}",
        )

    def test_webhook(self, partner_id: str, webhook_id: str) -> dict[str, Any]:
        """Send a test event to webhook."""
        return self._make_request(
            "POST",
            f"/api/v1/partners/{partner_id}/webhooks/{webhook_id}/test",
        )

    # ========================================================================
    # USAGE & ANALYTICS
    # ========================================================================

    def get_usage(
        self,
        partner_id: str,
        period: str = "current_month",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get partner usage statistics."""
        params = {"period": period}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return self._make_request(
            "GET",
            f"/api/v1/partners/{partner_id}/usage",
            params=params,
        )

    def get_daily_usage(
        self,
        partner_id: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get daily usage breakdown."""
        response = self._make_request(
            "GET",
            f"/api/v1/partners/{partner_id}/usage/daily",
            params={"days": days},
        )
        return response if isinstance(response, list) else response.get("daily_usage", [])

    def get_quota(self, partner_id: str) -> dict[str, Any]:
        """Get partner quota and usage."""
        return self._make_request(
            "GET",
            f"/api/v1/partners/{partner_id}/quota",
        )

    # ========================================================================
    # SUPPORT TICKETS
    # ========================================================================

    def create_support_ticket(
        self,
        partner_id: str,
        subject: str,
        description: str,
        priority: str = "normal",
        category: str = "general",
        attachments: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a support ticket."""
        payload = {
            "subject": subject,
            "description": description,
            "priority": priority,
            "category": category,
            "attachments": attachments,
        }
        return self._make_request(
            "POST",
            f"/api/v1/partners/{partner_id}/support/tickets",
            json=payload,
        )

    def list_support_tickets(
        self,
        partner_id: str,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List support tickets."""
        params = {"skip": skip, "limit": limit}
        if status_filter:
            params["status_filter"] = status_filter
        if priority_filter:
            params["priority_filter"] = priority_filter

        response = self._make_request(
            "GET",
            f"/api/v1/partners/{partner_id}/support/tickets",
            params=params,
        )
        return response if isinstance(response, list) else response.get("tickets", [])

    def get_support_ticket(self, partner_id: str, ticket_id: str) -> dict[str, Any]:
        """Get support ticket details."""
        return self._make_request(
            "GET",
            f"/api/v1/partners/{partner_id}/support/tickets/{ticket_id}",
        )

    def update_support_ticket(
        self,
        partner_id: str,
        ticket_id: str,
        **updates: Any,
    ) -> dict[str, Any]:
        """Update support ticket."""
        return self._make_request(
            "PATCH",
            f"/api/v1/partners/{partner_id}/support/tickets/{ticket_id}",
            json=updates,
        )

    # ========================================================================
    # DASHBOARD & HEALTH
    # ========================================================================

    def get_dashboard(self, partner_id: str) -> dict[str, Any]:
        """Get partner dashboard data."""
        return self._make_request(
            "GET",
            f"/api/v1/partners/{partner_id}/dashboard",
        )

    def get_health(self, partner_id: str) -> dict[str, Any]:
        """Get partner integration health status."""
        return self._make_request(
            "GET",
            f"/api/v1/partners/{partner_id}/health",
        )

    # ========================================================================
    # WEBHOOK VERIFICATION
    # ========================================================================

    @staticmethod
    def verify_webhook_signature(
        request_body: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verify webhook signature.

        Args:
            request_body: Raw request body bytes
            signature: Signature from X-Webhook-Signature header
            secret: Webhook secret

        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature = hmac.new(
            secret.encode(),
            request_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Register partner and create API key
    with PartnerClient(api_key="xag_partner_xxx") as client:
        # Register partner
        partner = client.register_partner(
            company_name="Acme Corp",
            contact_email="contact@acme.com",
            contact_name="John Doe",
            integration_type="standard",
        )
        print(f"Partner registered: {partner['partner_id']}")

        # Create API key
        api_key = client.create_api_key(
            partner_id=partner["partner_id"],
            name="Production Key",
            expires_in_days=365,
        )
        print(f"API key created: {api_key['key_prefix']}")

        # Register webhook
        webhook = client.register_webhook(
            partner_id=partner["partner_id"],
            event_type="partner.api_key.created",
            url="https://acme.com/webhooks/xagent",
        )
        print(f"Webhook registered: {webhook['webhook_id']}")

        # Get usage
        usage = client.get_usage(partner_id=partner["partner_id"])
        print(f"Usage: {usage['total_requests']} requests")
