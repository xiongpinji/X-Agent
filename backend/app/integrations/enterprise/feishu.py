"""Feishu (飞书) Integration Module"""

import json
from datetime import datetime
from typing import Any

import aiohttp

from .base import EnterpriseIMPlatform, MessageType


class FeishuIntegration(EnterpriseIMPlatform):
    """Feishu enterprise IM platform integration"""

    def __init__(self, app_id: str, app_secret: str):
        super().__init__("feishu")
        self.app_id = app_id
        self.app_secret = app_secret
        self.tenant_access_token: str | None = None
        self.token_expire_time: datetime | None = None
        self.base_url = "https://open.feishu.cn/open-apis"
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def authenticate(self) -> bool:
        """Authenticate with Feishu API"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret,
            }

            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("code") == 0:
                        self.tenant_access_token = data.get("tenant_access_token")
                        expire_in = data.get("expire", 7200)
                        self.token_expire_time = datetime.now().timestamp() + expire_in
                        self.is_connected = True
                        return True
            return False
        except Exception as e:
            print(f"Feishu authentication failed: {e}")
            return False

    async def _ensure_token(self) -> bool:
        """Ensure access token is valid"""
        if self.tenant_access_token is None or (
            self.token_expire_time and datetime.now().timestamp() > self.token_expire_time
        ):
            return await self.authenticate()
        return True

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authorization"""
        return {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    async def send_message(
        self, user_id: str, message: str, msg_type: MessageType = MessageType.TEXT
    ) -> bool:
        """Send a message to a user"""
        if not await self._ensure_token():
            return False

        try:
            session = await self._get_session()
            url = f"{self.base_url}/im/v1/messages"
            params = {
                "receive_id_type": "user_id",
            }

            payload = {
                "receive_id": user_id,
                "msg_type": "text",
                "content": json.dumps({"text": message}),
            }

            async with session.post(
                url, json=payload, params=params, headers=self._get_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("code") == 0
            return False
        except Exception as e:
            print(f"Feishu send_message failed: {e}")
            return False

    async def send_card(self, user_id: str, card: dict[str, Any]) -> bool:
        """Send a card message to a user"""
        if not await self._ensure_token():
            return False

        try:
            session = await self._get_session()
            url = f"{self.base_url}/im/v1/messages"
            params = {
                "receive_id_type": "user_id",
            }

            payload = {
                "receive_id": user_id,
                "msg_type": "interactive",
                "content": json.dumps({"elements": [card]}),
            }

            async with session.post(
                url, json=payload, params=params, headers=self._get_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("code") == 0
            return False
        except Exception as e:
            print(f"Feishu send_card failed: {e}")
            return False

    async def send_markdown(self, user_id: str, title: str, text: str) -> bool:
        """Send a markdown message to a user"""
        if not await self._ensure_token():
            return False

        try:
            session = await self._get_session()
            url = f"{self.base_url}/im/v1/messages"
            params = {
                "receive_id_type": "user_id",
            }

            payload = {
                "receive_id": user_id,
                "msg_type": "post",
                "content": json.dumps({
                    "zh_cn": {
                        "title": title,
                        "content": [[{"tag": "text", "text": text}]],
                    }
                }),
            }

            async with session.post(
                url, json=payload, params=params, headers=self._get_headers()
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("code") == 0
            return False
        except Exception as e:
            print(f"Feishu send_markdown failed: {e}")
            return False

    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """Get user information"""
        if not await self._ensure_token():
            return {}

        try:
            session = await self._get_session()
            url = f"{self.base_url}/contact/v3/users/{user_id}"

            async with session.get(url, headers=self._get_headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("code") == 0:
                        return data.get("data", {}).get("user", {})
            return {}
        except Exception as e:
            print(f"Feishu get_user_info failed: {e}")
            return {}

    async def sync_contacts(self) -> list[dict[str, Any]]:
        """Sync contacts from Feishu"""
        if not await self._ensure_token():
            return []

        try:
            users = []
            session = await self._get_session()
            url = f"{self.base_url}/contact/v3/users"
            params = {
                "page_size": 100,
                "page_token": "",
            }

            while True:
                async with session.get(url, params=params, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == 0:
                            result = data.get("data", {})
                            users.extend(result.get("items", []))
                            if not result.get("has_more"):
                                break
                            params["page_token"] = result.get("page_token", "")
                        else:
                            break
                    else:
                        break

            self.last_sync_time = datetime.now()
            return users
        except Exception as e:
            print(f"Feishu sync_contacts failed: {e}")
            return []

    async def sync_departments(self) -> list[dict[str, Any]]:
        """Sync departments from Feishu"""
        if not await self._ensure_token():
            return []

        try:
            departments = []
            session = await self._get_session()
            url = f"{self.base_url}/contact/v3/departments"
            params = {
                "page_size": 100,
                "page_token": "",
            }

            while True:
                async with session.get(url, params=params, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == 0:
                            result = data.get("data", {})
                            departments.extend(result.get("items", []))
                            if not result.get("has_more"):
                                break
                            params["page_token"] = result.get("page_token", "")
                        else:
                            break
                    else:
                        break

            self.last_sync_time = datetime.now()
            return departments
        except Exception as e:
            print(f"Feishu sync_departments failed: {e}")
            return []

    async def create_approval(self, template_id: str, data: dict[str, Any]) -> str:
        """Create an approval workflow instance"""
        if not await self._ensure_token():
            return ""

        try:
            session = await self._get_session()
            url = f"{self.base_url}/approval/openapi/v2/instances"

            payload = {
                "approval_code": template_id,
                "user_id": data.get("user_id"),
                "form": data.get("form_data", {}),
            }

            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("code") == 0:
                        return result.get("data", {}).get("instance_id", "")
            return ""
        except Exception as e:
            print(f"Feishu create_approval failed: {e}")
            return ""

    async def get_approval_status(self, approval_id: str) -> dict[str, Any]:
        """Get approval workflow status"""
        if not await self._ensure_token():
            return {}

        try:
            session = await self._get_session()
            url = f"{self.base_url}/approval/openapi/v2/instances/{approval_id}"

            async with session.get(url, headers=self._get_headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("code") == 0:
                        return data.get("data", {})
            return {}
        except Exception as e:
            print(f"Feishu get_approval_status failed: {e}")
            return {}

    async def upload_file(self, file_path: str, file_type: str) -> str:
        """Upload a file to Feishu"""
        if not await self._ensure_token():
            return ""

        try:
            session = await self._get_session()
            url = f"{self.base_url}/im/v1/files"

            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("file_type", file_type)
                data.add_field("file", f, filename=file_path.split("/")[-1])

                async with session.post(url, data=data, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("code") == 0:
                            return result.get("data", {}).get("file_key", "")
            return ""
        except Exception as e:
            print(f"Feishu upload_file failed: {e}")
            return ""

    async def download_file(self, file_id: str) -> bytes:
        """Download a file from Feishu"""
        if not await self._ensure_token():
            return b""

        try:
            session = await self._get_session()
            url = f"{self.base_url}/im/v1/files/{file_id}/download"

            async with session.get(url, headers=self._get_headers()) as resp:
                if resp.status == 200:
                    return await resp.read()
            return b""
        except Exception as e:
            print(f"Feishu download_file failed: {e}")
            return b""

    async def send_bot_message(self, webhook_url: str, message: dict[str, Any]) -> bool:
        """Send a message via Feishu bot webhook"""
        try:
            session = await self._get_session()
            async with session.post(webhook_url, json=message) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("code") == 0
            return False
        except Exception as e:
            print(f"Feishu send_bot_message failed: {e}")
            return False

    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()
