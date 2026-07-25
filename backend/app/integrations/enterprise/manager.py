"""Enterprise IM Platform Manager"""

from typing import Any

from .base import EnterpriseIMPlatform, MessageType
from .dingtalk import DingTalkIntegration
from .feishu import FeishuIntegration
from .wechat_work import WeChatWorkIntegration


class EnterpriseIMManager:
    """Unified manager for enterprise IM platforms"""

    def __init__(self):
        self.platforms: dict[str, EnterpriseIMPlatform] = {}
        self.platform_configs: dict[str, dict[str, Any]] = {}

    def register_platform(self, name: str, platform: EnterpriseIMPlatform, config: dict[str, Any] | None = None):
        """Register a platform instance"""
        self.platforms[name] = platform
        if config:
            self.platform_configs[name] = config

    def unregister_platform(self, name: str):
        """Unregister a platform instance"""
        if name in self.platforms:
            del self.platforms[name]
        if name in self.platform_configs:
            del self.platform_configs[name]

    def get_platform(self, name: str) -> EnterpriseIMPlatform | None:
        """Get a platform instance"""
        return self.platforms.get(name)

    def list_platforms(self) -> list[str]:
        """List all registered platforms"""
        return list(self.platforms.keys())

    async def create_dingtalk_platform(
        self, app_key: str, app_secret: str, corp_id: str | None = None
    ) -> bool:
        """Create and register DingTalk platform"""
        try:
            platform = DingTalkIntegration(app_key, app_secret, corp_id)
            if await platform.authenticate():
                self.register_platform("dingtalk", platform, {
                    "app_key": app_key,
                    "corp_id": corp_id,
                })
                return True
            return False
        except Exception as e:
            print(f"Failed to create DingTalk platform: {e}")
            return False

    async def create_feishu_platform(self, app_id: str, app_secret: str) -> bool:
        """Create and register Feishu platform"""
        try:
            platform = FeishuIntegration(app_id, app_secret)
            if await platform.authenticate():
                self.register_platform("feishu", platform, {
                    "app_id": app_id,
                })
                return True
            return False
        except Exception as e:
            print(f"Failed to create Feishu platform: {e}")
            return False

    async def create_wechat_work_platform(
        self, corp_id: str, corp_secret: str, agent_id: str | None = None
    ) -> bool:
        """Create and register WeChat Work platform"""
        try:
            platform = WeChatWorkIntegration(corp_id, corp_secret, agent_id)
            if await platform.authenticate():
                self.register_platform("wechat_work", platform, {
                    "corp_id": corp_id,
                    "agent_id": agent_id,
                })
                return True
            return False
        except Exception as e:
            print(f"Failed to create WeChat Work platform: {e}")
            return False

    async def send_message_to_platform(
        self,
        platform_name: str,
        user_id: str,
        message: str,
        msg_type: MessageType = MessageType.TEXT,
    ) -> bool:
        """Send a message to a user on a specific platform"""
        platform = self.get_platform(platform_name)
        if not platform:
            return False

        try:
            return await platform.send_message(user_id, message, msg_type)
        except Exception as e:
            print(f"Failed to send message on {platform_name}: {e}")
            return False

    async def send_message_to_all(
        self,
        user_mappings: dict[str, str],
        message: str,
        msg_type: MessageType = MessageType.TEXT,
    ) -> dict[str, bool]:
        """Send a message to all platforms"""
        results = {}
        for platform_name, user_id in user_mappings.items():
            results[platform_name] = await self.send_message_to_platform(
                platform_name, user_id, message, msg_type
            )
        return results

    async def send_card_to_platform(
        self, platform_name: str, user_id: str, card: dict[str, Any]
    ) -> bool:
        """Send a card message to a user on a specific platform"""
        platform = self.get_platform(platform_name)
        if not platform:
            return False

        try:
            return await platform.send_card(user_id, card)
        except Exception as e:
            print(f"Failed to send card on {platform_name}: {e}")
            return False

    async def send_markdown_to_platform(
        self, platform_name: str, user_id: str, title: str, text: str
    ) -> bool:
        """Send a markdown message to a user on a specific platform"""
        platform = self.get_platform(platform_name)
        if not platform:
            return False

        try:
            return await platform.send_markdown(user_id, title, text)
        except Exception as e:
            print(f"Failed to send markdown on {platform_name}: {e}")
            return False

    async def sync_contacts_from_all(self) -> dict[str, list[dict[str, Any]]]:
        """Sync contacts from all platforms"""
        results = {}
        for platform_name, platform in self.platforms.items():
            try:
                results[platform_name] = await platform.sync_contacts()
            except Exception as e:
                print(f"Failed to sync contacts from {platform_name}: {e}")
                results[platform_name] = []
        return results

    async def sync_departments_from_all(self) -> dict[str, list[dict[str, Any]]]:
        """Sync departments from all platforms"""
        results = {}
        for platform_name, platform in self.platforms.items():
            try:
                results[platform_name] = await platform.sync_departments()
            except Exception as e:
                print(f"Failed to sync departments from {platform_name}: {e}")
                results[platform_name] = []
        return results

    async def get_user_info_from_platform(
        self, platform_name: str, user_id: str
    ) -> dict[str, Any]:
        """Get user info from a specific platform"""
        platform = self.get_platform(platform_name)
        if not platform:
            return {}

        try:
            return await platform.get_user_info(user_id)
        except Exception as e:
            print(f"Failed to get user info from {platform_name}: {e}")
            return {}

    async def create_approval_on_platform(
        self, platform_name: str, template_id: str, data: dict[str, Any]
    ) -> str:
        """Create an approval on a specific platform"""
        platform = self.get_platform(platform_name)
        if not platform:
            return ""

        try:
            return await platform.create_approval(template_id, data)
        except Exception as e:
            print(f"Failed to create approval on {platform_name}: {e}")
            return ""

    async def get_approval_status_from_platform(
        self, platform_name: str, approval_id: str
    ) -> dict[str, Any]:
        """Get approval status from a specific platform"""
        platform = self.get_platform(platform_name)
        if not platform:
            return {}

        try:
            return await platform.get_approval_status(approval_id)
        except Exception as e:
            print(f"Failed to get approval status from {platform_name}: {e}")
            return {}

    async def upload_file_to_platform(
        self, platform_name: str, file_path: str, file_type: str
    ) -> str:
        """Upload a file to a specific platform"""
        platform = self.get_platform(platform_name)
        if not platform:
            return ""

        try:
            return await platform.upload_file(file_path, file_type)
        except Exception as e:
            print(f"Failed to upload file to {platform_name}: {e}")
            return ""

    async def download_file_from_platform(
        self, platform_name: str, file_id: str
    ) -> bytes:
        """Download a file from a specific platform"""
        platform = self.get_platform(platform_name)
        if not platform:
            return b""

        try:
            return await platform.download_file(file_id)
        except Exception as e:
            print(f"Failed to download file from {platform_name}: {e}")
            return b""

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all platforms"""
        results = {}
        for platform_name, platform in self.platforms.items():
            try:
                results[platform_name] = await platform.health_check()
            except Exception as e:
                print(f"Health check failed for {platform_name}: {e}")
                results[platform_name] = False
        return results

    def get_connection_status_all(self) -> dict[str, dict[str, Any]]:
        """Get connection status of all platforms"""
        results = {}
        for platform_name, platform in self.platforms.items():
            results[platform_name] = platform.get_connection_status()
        return results

    async def close_all(self):
        """Close all platform connections"""
        for platform in self.platforms.values():
            try:
                await platform.close()
            except Exception as e:
                print(f"Failed to close platform: {e}")
