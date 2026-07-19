"""DingTalk (钉钉) Integration Module"""

import hashlib
import hmac
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiohttp

from .base import EnterpriseIMPlatform, MessageType


class DingTalkIntegration(EnterpriseIMPlatform):
    """DingTalk enterprise IM platform integration"""

    def __init__(self, app_key: str, app_secret: str, corp_id: str = None):
        super().__init__("dingtalk")
        self.app_key = app_key
        self.app_secret = app_secret
        self.corp_id = corp_id
        self.access_token: Optional[str] = None
        self.token_expire_time: Optional[datetime] = None
        self.base_url = "https://oapi.dingtalk.com"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def authenticate(self) -> bool:
        """Authenticate with DingTalk API"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/gettoken"
            params = {
                "appkey": self.app_key,
                "appsecret": self.app_secret,
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
            print(f"DingTalk authentication failed: {e}")
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
            url = f"{self.base_url}/topapi/message/corpconversation/asyncsend_v2"
            params = {"access_token": self.access_token}

            payload = {
                "receiver_type": "userid",
                "receiver_id": user_id,
                "sender": "X-Agent",
                "msg": {
                    "msgtype": "text",
                    "text": {"content": message},
                },
            }

            async with session.post(url, json=payload, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("errcode") == 0
            return False
        except Exception as e:
            print(f"DingTalk send_message failed: {e}")
            return False

    async def send_card(self, user_id: str, card: Dict[str, Any]) -> bool:
        """Send a card message to a user"""
        if not await self._ensure_token():
            return False

        try:
            session = await self._get_session()
            url = f"{self.base_url}/topapi/message/corpconversation/asyncsend_v2"
            params = {"access_token": self.access_token}

            payload = {
                "receiver_type": "userid",
                "receiver_id": user_id,
                "sender": "X-Agent",
                "msg": {
                    "msgtype": "action_card",
                    "action_card": card,
                },
            }

            async with session.post(url, json=payload, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("errcode") == 0
            return False
        except Exception as e:
            print(f"DingTalk send_card failed: {e}")
            return False

    async def send_markdown(self, user_id: str, title: str, text: str) -> bool:
        """Send a markdown message to a user"""
        if not await self._ensure_token():
            return False

        try:
            session = await self._get_session()
            url = f"{self.base_url}/topapi/message/corpconversation/asyncsend_v2"
            params = {"access_token": self.access_token}

            payload = {
                "receiver_type": "userid",
                "receiver_id": user_id,
                "sender": "X-Agent",
                "msg": {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": title,
                        "text": text,
                    },
                },
            }

            async with session.post(url, json=payload, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("errcode") == 0
            return False
        except Exception as e:
            print(f"DingTalk send_markdown failed: {e}")
            return False

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information"""
        if not await self._ensure_token():
            return {}

        try:
            session = await self._get_session()
            url = f"{self.base_url}/topapi/v2/user/get"
            params = {
                "access_token": self.access_token,
                "userid": user_id,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("errcode") == 0:
                        return data.get("result", {})
            return {}
        except Exception as e:
            print(f"DingTalk get_user_info failed: {e}")
            return {}

    async def sync_contacts(self) -> List[Dict[str, Any]]:
        """Sync contacts from DingTalk"""
        if not await self._ensure_token():
            return []

        try:
            users = []
            session = await self._get_session()
            url = f"{self.base_url}/topapi/v2/user/list"
            params = {
                "access_token": self.access_token,
                "dept_id": 1,
                "cursor": 0,
                "size": 100,
            }

            while True:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("errcode") == 0:
                            result = data.get("result", {})
                            users.extend(result.get("list", []))
                            if not result.get("has_more"):
                                break
                            params["cursor"] = result.get("next_cursor")
                        else:
                            break
                    else:
                        break

            self.last_sync_time = datetime.now()
            return users
        except Exception as e:
            print(f"DingTalk sync_contacts failed: {e}")
            return []

    async def sync_departments(self) -> List[Dict[str, Any]]:
        """Sync departments from DingTalk"""
        if not await self._ensure_token():
            return []

        try:
            departments = []
            session = await self._get_session()
            url = f"{self.base_url}/topapi/v2/department/listsub"
            params = {
                "access_token": self.access_token,
                "dept_id": 1,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("errcode") == 0:
                        departments = data.get("result", {}).get("dept_list", [])

            self.last_sync_time = datetime.now()
            return departments
        except Exception as e:
            print(f"DingTalk sync_departments failed: {e}")
            return []

    async def create_approval(self, template_id: str, data: Dict[str, Any]) -> str:
        """Create an approval workflow instance"""
        if not await self._ensure_token():
            return ""

        try:
            session = await self._get_session()
            url = f"{self.base_url}/topapi/processinstance/create"
            params = {"access_token": self.access_token}

            payload = {
                "process_code": template_id,
                "originator_user_id": data.get("originator_user_id"),
                "form_component_values": data.get("form_data", []),
                "approvers": data.get("approvers", []),
            }

            async with session.post(url, json=payload, params=params) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("errcode") == 0:
                        return result.get("result", {}).get("process_instance_id", "")
            return ""
        except Exception as e:
            print(f"DingTalk create_approval failed: {e}")
            return ""

    async def get_approval_status(self, approval_id: str) -> Dict[str, Any]:
        """Get approval workflow status"""
        if not await self._ensure_token():
            return {}

        try:
            session = await self._get_session()
            url = f"{self.base_url}/topapi/processinstance/get"
            params = {
                "access_token": self.access_token,
                "process_instance_id": approval_id,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("errcode") == 0:
                        return data.get("result", {})
            return {}
        except Exception as e:
            print(f"DingTalk get_approval_status failed: {e}")
            return {}

    async def upload_file(self, file_path: str, file_type: str) -> str:
        """Upload a file to DingTalk"""
        if not await self._ensure_token():
            return ""

        try:
            session = await self._get_session()
            url = f"{self.base_url}/topapi/media/upload"
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
            print(f"DingTalk upload_file failed: {e}")
            return ""

    async def download_file(self, file_id: str) -> bytes:
        """Download a file from DingTalk"""
        if not await self._ensure_token():
            return b""

        try:
            session = await self._get_session()
            url = f"{self.base_url}/topapi/media/download"
            params = {
                "access_token": self.access_token,
                "media_id": file_id,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.read()
            return b""
        except Exception as e:
            print(f"DingTalk download_file failed: {e}")
            return b""

    async def send_robot_message(self, webhook_url: str, message: Dict[str, Any]) -> bool:
        """Send a message via DingTalk robot webhook"""
        try:
            session = await self._get_session()
            timestamp = str(int(time.time() * 1000))
            sign = self._generate_sign(timestamp)

            url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
            async with session.post(url, json=message) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("errcode") == 0
            return False
        except Exception as e:
            print(f"DingTalk send_robot_message failed: {e}")
            return False

    def _generate_sign(self, timestamp: str) -> str:
        """Generate signature for DingTalk robot webhook"""
        message = f"{timestamp}\n{self.app_secret}"
        sign = hmac.new(
            self.app_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).digest()
        import base64
        return base64.b64encode(sign).decode()

    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()
