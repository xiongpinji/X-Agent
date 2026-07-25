"""GitHub integration — webhook receiver + minimal API client for the
Issue-to-PR pipeline.

The webhook endpoint validates the HMAC signature (when a secret is set),
parses `issues.assigned` / `issues.opened` events, and enqueues a task for
the sandbox orchestrator. The API client creates PRs via the REST API using
httpx (already a dependency).

Security:
- Signature verification uses constant-time comparison (hmac.compare_digest).
- The webhook NEVER executes instructions from issue bodies directly; it only
  enqueues a task whose payload is the issue metadata. The agent decides what
  to do downstream under normal policy/approval gates.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify a GitHub webhook HMAC-SHA256 signature.

    signature_header looks like 'sha256=<hex>'. Returns False on any mismatch
    or malformed input. Constant-time comparison prevents timing attacks.
    """
    if not signature_header or not secret:
        return False
    try:
        algo, sig = signature_header.split("=", 1)
    except ValueError:
        return False
    if algo != "sha256":
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@dataclass
class IssueEvent:
    """Parsed GitHub issue event relevant to the pipeline."""

    action: str
    repo_full_name: str
    issue_number: int
    title: str
    body: str
    labels: list[str]
    clone_url: str
    default_branch: str = "main"


def parse_issue_event(payload: dict[str, Any]) -> IssueEvent | None:
    """Extract an IssueEvent from a GitHub webhook payload, or None if not
    an actionable issue event."""
    if "issue" not in payload or "repository" not in payload:
        return None
    action = payload.get("action", "")
    if action not in ("assigned", "opened", "labeled"):
        return None
    issue = payload["issue"]
    repo = payload["repository"]
    return IssueEvent(
        action=action,
        repo_full_name=repo.get("full_name", ""),
        issue_number=issue.get("number", 0),
        title=issue.get("title", ""),
        body=issue.get("body") or "",
        labels=[lbl.get("name", "") for lbl in issue.get("labels", [])],
        clone_url=repo.get("clone_url", ""),
        default_branch=repo.get("default_branch", "main"),
    )


class GitHubAPIClient:
    """Minimal GitHub REST client (PR creation + comments) over httpx."""

    def __init__(self, token: str, base_url: str = "https://api.github.com"):
        self._token = token
        self._base = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def create_pull_request(
        self,
        repo_full_name: str,
        head: str,
        base: str,
        title: str,
        body: str = "",
    ) -> dict[str, Any]:
        """Open a PR. Returns the API response dict (contains html_url, number)."""
        import httpx

        url = f"{self._base}/repos/{repo_full_name}/pulls"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={"title": title, "head": head, "base": base, "body": body},
            )
            resp.raise_for_status()
            return resp.json()

    async def comment_on_issue(
        self, repo_full_name: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        """Post a comment on an issue or PR."""
        import httpx

        url = f"{self._base}/repos/{repo_full_name}/issues/{issue_number}/comments"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=self._headers(), json={"body": body})
            resp.raise_for_status()
            return resp.json()

    def authenticated_clone_url(self, clone_url: str) -> str:
        """Embed the token into an https clone URL for push access."""
        if clone_url.startswith("https://"):
            return clone_url.replace(
                "https://", f"https://x-access-token:{self._token}@", 1
            )
        return clone_url
