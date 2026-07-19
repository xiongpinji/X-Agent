"""GitHub MCP Plugin - Manage GitHub repositories, issues, and pull requests"""

import logging
from typing import Any, Optional
import requests
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


class GitHubPlugin:
    """GitHub MCP Plugin Server"""

    def __init__(self, config: dict[str, Any] = None):
        """Initialize GitHub plugin"""
        self.config = config or {}
        self.token = self.config.get("github_token")
        self.timeout = self.config.get("timeout", 30)

        if not self.token:
            raise ValueError("github_token is required")

        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "X-Agent-GitHub-Plugin"
        }

        logger.info("GitHubPlugin initialized")

    async def list_repositories(self, username: str, limit: int = 10) -> dict[str, Any]:
        """List user repositories"""
        try:
            url = f"{self.base_url}/users/{username}/repos"
            params = {"per_page": min(limit, 100), "sort": "updated"}

            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()

            repos = response.json()
            return {
                "status": "success",
                "data": [
                    {
                        "name": repo["name"],
                        "url": repo["html_url"],
                        "description": repo["description"],
                        "stars": repo["stargazers_count"],
                        "language": repo["language"],
                        "updated_at": repo["updated_at"]
                    }
                    for repo in repos[:limit]
                ],
                "count": len(repos)
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list repositories: {e}")
            return {
                "status": "error",
                "message": f"Failed to list repositories: {str(e)}"
            }

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository information"""
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}"

            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            repo_data = response.json()
            return {
                "status": "success",
                "data": {
                    "name": repo_data["name"],
                    "url": repo_data["html_url"],
                    "description": repo_data["description"],
                    "stars": repo_data["stargazers_count"],
                    "forks": repo_data["forks_count"],
                    "language": repo_data["language"],
                    "topics": repo_data["topics"],
                    "created_at": repo_data["created_at"],
                    "updated_at": repo_data["updated_at"],
                    "default_branch": repo_data["default_branch"]
                }
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get repository: {e}")
            return {
                "status": "error",
                "message": f"Failed to get repository: {str(e)}"
            }

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = ""
    ) -> dict[str, Any]:
        """Create an issue"""
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/issues"
            data = {
                "title": title,
                "body": body
            }

            response = requests.post(
                url,
                headers=self.headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()

            issue = response.json()
            return {
                "status": "success",
                "data": {
                    "number": issue["number"],
                    "title": issue["title"],
                    "url": issue["html_url"],
                    "state": issue["state"],
                    "created_at": issue["created_at"]
                }
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create issue: {e}")
            return {
                "status": "error",
                "message": f"Failed to create issue: {str(e)}"
            }

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        limit: int = 10
    ) -> dict[str, Any]:
        """List repository issues"""
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/issues"
            params = {
                "state": state,
                "per_page": min(limit, 100),
                "sort": "updated"
            }

            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()

            issues = response.json()
            return {
                "status": "success",
                "data": [
                    {
                        "number": issue["number"],
                        "title": issue["title"],
                        "url": issue["html_url"],
                        "state": issue["state"],
                        "created_at": issue["created_at"],
                        "updated_at": issue["updated_at"]
                    }
                    for issue in issues[:limit]
                ],
                "count": len(issues)
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list issues: {e}")
            return {
                "status": "error",
                "message": f"Failed to list issues: {str(e)}"
            }

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = ""
    ) -> dict[str, Any]:
        """Create a pull request"""
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
            data = {
                "title": title,
                "head": head,
                "base": base,
                "body": body
            }

            response = requests.post(
                url,
                headers=self.headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()

            pr = response.json()
            return {
                "status": "success",
                "data": {
                    "number": pr["number"],
                    "title": pr["title"],
                    "url": pr["html_url"],
                    "state": pr["state"],
                    "created_at": pr["created_at"]
                }
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create pull request: {e}")
            return {
                "status": "error",
                "message": f"Failed to create pull request: {str(e)}"
            }

    async def handle_tool_call(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Handle tool calls"""
        try:
            if tool_name == "list_repositories":
                return await self.list_repositories(**args)
            elif tool_name == "get_repository":
                return await self.get_repository(**args)
            elif tool_name == "create_issue":
                return await self.create_issue(**args)
            elif tool_name == "list_issues":
                return await self.list_issues(**args)
            elif tool_name == "create_pull_request":
                return await self.create_pull_request(**args)
            else:
                return {
                    "status": "error",
                    "message": f"Unknown tool: {tool_name}"
                }
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "status": "error",
                "message": f"Tool execution error: {str(e)}"
            }


# Entry point for MCP server
if __name__ == "__main__":
    import asyncio

    # Example usage
    config = {
        "github_token": "your-token-here"
    }

    plugin = GitHubPlugin(config)

    # Test
    result = asyncio.run(plugin.list_repositories("torvalds", limit=5))
    print(result)
