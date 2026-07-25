"""WeChat Work (企业微信) Integration Module"""

from datetime import datetime
from typing import Any

import aiohttp

from .base import EnterpriseIMPlatform, MessageType


class WeChatWorkIntegration(EnterpriseIMPlatform):
    """WeChat Work enterprise IM platform integration"""

    def __init__(self, corp_id: str, corp_secret: str, agent_id: str | None = None):
        super().__init__("wechat_work")
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = agent_id
        self.access_token: str | None = None
        self.token_expire_time: datetime | None = None
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def authenticate(self) -> bool:
        """Authenticate with WeChat Work API"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/gettoken"
            params = {
                "corpid": self.corp_id,
                "corpsecret": self.corp_secret,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("errcode") == 0:
                        self.access_token = data.get("access_token")
                        expire_in = data.get("expires_in", 7200)
                        self.token_expire_time = datetime.now().timestamp() + expire_in
                        self.is_connected = True
                        return True
            return False
        except Exception as e:
            print(f"WeChat Work authentication failed: {e}")
            return False

    async def _ensure_token(self) -> bool:
        """Ensure access token is valid"""
        if self.access_token is None or (
            self.token_expire_time and datetime.now().timestamp() > self.token_expire_time
        ):
            return await self.authenticate()
        return True

    async def send_message(
        self, user_id: str, message: str, msg_type: MessageType = MessageType.TEXT
    ) -> bool:
        """Send a message to a user"""
        if not await self._ensure_token():
            return False

        try:
            session = await self._get_session()
            url = f"{self.base_url}/message/send"
            params = {"access_token": self.access_token}

            payload = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": self.agent_id,
                "text": {"content": message},
                "safe": 0,
            }

            async with session.post(url, json=payload, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("errcode") == 0
            return False
        except Exception as e:
            print(f"WeChat Work send_message failed: {e}")
            return False

    async def send_card(self, user_id: str, card: dict[str, Any]) -> bool:
        """Send a card message to a user"""
        if not await self._ensure_token():
            return False

        try:
            session = await self._get_session()
            url = f"{self.base_url}/message/send"
            params = {"access_token": self.access_token}

            payload = {
                "touser": user_id,
                "msgtype": "template_card",
                "agentid": self.agent_id,
                "template_card": card,
            }

            async with session.post(url, json=payload, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("errcode") == 0
            return False
        except Exception as e:
            print(f"WeChat Work send_card failed: {e}")
            return False

    async def send_markdown(self, user_id: str, title: str, text: str) -> bool:
        """Send a markdown message to a user"""
        if not await self._ensure_token():
            return False

        try:
            session = await self._get_session()
            url = f"{self.base_url}/message/send"
            params = {"access_token": self.access_token}

            payload = {
                "touser": user_id,
                "msgtype": "markdown",
                "agentid": self.agent_id,
                "markdown": {
                    "content": f"# {title}\n\n{text}",
                },
            }

            async with session.post(url, json=payload, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("errcode") == 0
            return False
        except Exception as e:
            print(f"WeChat Work send_markdown failed: {e}")
            return False

    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """Get user information"""
        if not await self._ensure_token():
            return {}

        try:
            session = await self._get_session()
            url = f"{self.base_url}/user/get"
            params = {
                "access_token": self.access_token,
                "userid": user_id,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("errcode") == 0:
                        return data
            return {}
        except Exception as e:
            print(f"WeChat Work get_user_info failed: {e}")
            return {}

    async def sync_contacts(self) -> list[dict[str, Any]]:
        """Sync contacts from WeChat Work"""
        if not await self._ensure_token():
            return []

        try:
            users = []
            session = await self._get_session()
            url = f"{self.base_url}/user/list"
            params = {
                "access_token": self.access_token,
                "department_id": 1,
                "fetch_child": 1,
                "simple": 0,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("errcode") == 0:
                        users = data.get("userlist", [])

            self.last_sync_time = datetime.now()
            return users
        except Exception as e:
            print(f"WeChat Work sync_contacts failed: {e}")
            return []

    async def sync_departments(self) -> list[dict[str, Any]]:
        """Sync departments from WeChat Work"""
        if not await self._ensure_token():
            return []

        try:
            departments = []
            session = await self._get_session()
            url = f"{self.base_url}/department/list"
            params = {
                "access_token": self.access_token,
                "id": 1,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("errcode") == 0:
                        departments = data.get("department", [])

            self.last_sync_time = datetime.now()
            return departments
        except Exception as e:
            print(f"WeChat Work sync_departments failed: {e}")
            return []

    async def create_approval(self, template_id: str, data: dict[str, Any]) -> str:
        """Create an approval workflow instance"""
        if not await self._ensure_token():
            return ""

        try:
            session = await self._get_session()
            url = f"{self.base_url}/oa/applyevent"
            params = {"access_token": self.access_token}

            payload = {
                "creator": data.get("creator"),
                "use_template_approver": 0,
                "choose_department": data.get("department_id", 1),
                "approver": data.get("approvers", []),
                "notifyer": data.get("notifiers", []),
                "apply_data": {
                    "contents": data.get("form_data", []),
                },
                "comments": data.get("comments", []),
            }

            async with session.post(url, json=payload, params=params) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("errcode") == 0:
                        return result.get("sp_no", "")
            return ""
        except Exception as e:
            print(f"WeChat Work create_approval failed: {e}")
            return ""

    async def get_approval_status(self, approval_id: str) -> dict[str, Any]:
        """Get approval workflow status"""
        if not await self._ensure_token():
            return {}

        try:
            session = await self._get_session()
            url = f"{self.base_url}/oa/gettripleinfo"
            params = {"access_token": self.access_token}

            payload = {
                "sp_no": approval_id,
            }

            async with session.post(url, json=payload, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("errcode") == 0:
                        return data
            return {}
        except Exception as e:
            print(f"WeChat Work get_approval_status failed: {e}")
            return {}

    async def upload_file(self, file_path: str, file_type: str) -> str:
        """Upload a file to WeChat Work"""
        if not await self._ensure_token():
            return ""

        try:
            session = await self._get_session()
            url = f"{self.base_url}/media/upload"
            params = {
                "access_token": self.access_token,
                "type": file_type,
            }

            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("media", f, filename=file_path.split("/")[-1])

                async with session.post(url, data=data, params=params) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("errcode") == 0:
                            return result.get("media_id", "")
            return ""
        except Exception as e:
            print(f"WeChat Work upload_file failed: {e}")
            return ""

    async def download_file(self, file_id: str) -> bytes:
        """Download a file from WeChat Work"""
        if not await self._ensure_token():
            return b""

        try:
            session = await self._get_session()
            url = f"{self.base_url}/media/get"
            params = {
                "access_token": self.access_token,
                "media_id": file_id,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.read()
            return b""
        except Exception as e:
            print(f"WeChat Work download_file failed: {e}")
            return b""

    async def send_robot_message(self, webhook_url: str, message: dict[str, Any]) -> bool:
        """Send a message via WeChat Work robot webhook"""
        try:
            session = await self._get_session()
            async with session.post(webhook_url, json=message) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("errcode") == 0
            return False
        except Exception as e:
            print(f"WeChat Work send_robot_message failed: {e}")
            return False

    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()
