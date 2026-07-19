"""Network request and response monitoring for browser automation."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

try:
    from playwright.async_api import Page, Request, Response
except ImportError:
    Page = Request = Response = object  # type: ignore[assignment]


@dataclass
class NetworkRequest:
    """Represents an HTTP request."""
    url: str
    method: str
    headers: dict[str, str] = field(default_factory=dict)
    post_data: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    resource_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "post_data": self.post_data,
            "timestamp": self.timestamp,
            "resource_type": self.resource_type,
        }


@dataclass
class NetworkResponse:
    """Represents an HTTP response."""
    url: str
    status: int
    status_text: str
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    request_timestamp: float = 0.0

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds from request to response."""
        return (self.timestamp - self.request_timestamp) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "status_text": self.status_text,
            "headers": self.headers,
            "body": self.body,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }


class NetworkMonitor:
    """Monitors network requests and responses in a browser page."""

    def __init__(self, page: Page | None = None):
        self.page = page
        self._requests: dict[str, NetworkRequest] = {}
        self._responses: list[NetworkResponse] = []
        self._request_map: dict[str, float] = {}  # url -> request_timestamp
        self._listeners_attached = False

    async def start_monitoring(self, page: Page) -> None:
        """Start monitoring network activity on the given page."""
        self.page = page
        if self._listeners_attached:
            return

        # Listen to requests
        page.on("request", self._on_request)
        # Listen to responses
        page.on("response", self._on_response)
        self._listeners_attached = True

    async def stop_monitoring(self) -> None:
        """Stop monitoring network activity."""
        if self.page and self._listeners_attached:
            self.page.remove_listener("request", self._on_request)
            self.page.remove_listener("response", self._on_response)
            self._listeners_attached = False

    def _on_request(self, request: Request) -> None:
        """Handle request event."""
        try:
            url = request.url
            method = request.method
            headers = dict(request.headers)
            post_data = request.post_data
            resource_type = request.resource_type

            req = NetworkRequest(
                url=url,
                method=method,
                headers=headers,
                post_data=post_data,
                resource_type=resource_type,
            )
            self._requests[url] = req
            self._request_map[url] = req.timestamp
        except Exception:
            pass

    def _on_response(self, response: Response) -> None:
        """Handle response event."""
        try:
            url = response.url
            status = response.status
            status_text = response.status_text
            headers = dict(response.headers)

            resp = NetworkResponse(
                url=url,
                status=status,
                status_text=status_text,
                headers=headers,
                request_timestamp=self._request_map.get(url, time.time()),
            )
            self._responses.append(resp)
        except Exception:
            pass

    def get_requests(self, url_pattern: Optional[str] = None) -> list[NetworkRequest]:
        """Get all captured requests, optionally filtered by URL pattern."""
        requests = list(self._requests.values())

        if url_pattern:
            try:
                pattern = re.compile(url_pattern)
                requests = [r for r in requests if pattern.search(r.url)]
            except re.error:
                pass

        return sorted(requests, key=lambda r: r.timestamp)

    def get_responses(self, url_pattern: Optional[str] = None) -> list[NetworkResponse]:
        """Get all captured responses, optionally filtered by URL pattern."""
        responses = self._responses

        if url_pattern:
            try:
                pattern = re.compile(url_pattern)
                responses = [r for r in responses if pattern.search(r.url)]
            except re.error:
                pass

        return sorted(responses, key=lambda r: r.timestamp)

    def get_request_by_url(self, url: str) -> Optional[NetworkRequest]:
        """Get a specific request by URL."""
        return self._requests.get(url)

    def get_responses_by_url(self, url: str) -> list[NetworkResponse]:
        """Get all responses for a specific URL."""
        return [r for r in self._responses if r.url == url]

    def get_failed_requests(self) -> list[NetworkResponse]:
        """Get all failed responses (status >= 400)."""
        return [r for r in self._responses if r.status >= 400]

    def clear_history(self) -> None:
        """Clear all captured requests and responses."""
        self._requests.clear()
        self._responses.clear()
        self._request_map.clear()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of network activity."""
        total_requests = len(self._requests)
        total_responses = len(self._responses)
        failed_responses = len(self.get_failed_requests())

        total_duration = 0.0
        if self._responses:
            total_duration = sum(r.duration_ms for r in self._responses)

        return {
            "total_requests": total_requests,
            "total_responses": total_responses,
            "failed_responses": failed_responses,
            "total_duration_ms": total_duration,
            "average_response_time_ms": total_duration / total_responses if total_responses > 0 else 0,
        }
