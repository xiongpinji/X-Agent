"""Tests for Enterprise IM Integration"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.integrations.enterprise.base import EnterpriseIMPlatform, MessageType
from backend.app.integrations.enterprise.dingtalk import DingTalkIntegration
from backend.app.integrations.enterprise.feishu import FeishuIntegration
from backend.app.integrations.enterprise.wechat_work import WeChatWorkIntegration
from backend.app.integrations.enterprise.manager import EnterpriseIMManager
from backend.app.integrations.enterprise.message_router import MessageRouter, EventType
from backend.app.integrations.enterprise.user_mapping import UserMapping


class TestDingTalkIntegration:
    """Test DingTalk integration"""

    @pytest.mark.asyncio
    async def test_authenticate(self):
        """Test DingTalk authentication"""
        dingtalk = DingTalkIntegration("test_key", "test_secret")

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "errcode": 0,
                "access_token": "test_token",
                "expires_in": 7200,
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await dingtalk.authenticate()
            assert result is True
            assert dingtalk.access_token == "test_token"

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending message via DingTalk"""
        dingtalk = DingTalkIntegration("test_key", "test_secret")
        dingtalk.access_token = "test_token"
        dingtalk.token_expire_time = float("inf")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"errcode": 0})
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await dingtalk.send_message("user123", "Hello")
            assert result is True

    @pytest.mark.asyncio
    async def test_sync_contacts(self):
        """Test syncing contacts from DingTalk"""
        dingtalk = DingTalkIntegration("test_key", "test_secret")
        dingtalk.access_token = "test_token"
        dingtalk.token_expire_time = float("inf")

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "errcode": 0,
                "result": {
                    "list": [
                        {"userid": "user1", "name": "User 1"},
                        {"userid": "user2", "name": "User 2"},
                    ],
                    "has_more": False,
                },
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            contacts = await dingtalk.sync_contacts()
            assert len(contacts) == 2
            assert contacts[0]["userid"] == "user1"


class TestFeishuIntegration:
    """Test Feishu integration"""

    @pytest.mark.asyncio
    async def test_authenticate(self):
        """Test Feishu authentication"""
        feishu = FeishuIntegration("test_app_id", "test_app_secret")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "code": 0,
                "tenant_access_token": "test_token",
                "expire": 7200,
            })
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await feishu.authenticate()
            assert result is True
            assert feishu.tenant_access_token == "test_token"

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending message via Feishu"""
        feishu = FeishuIntegration("test_app_id", "test_app_secret")
        feishu.tenant_access_token = "test_token"
        feishu.token_expire_time = float("inf")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"code": 0})
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await feishu.send_message("user123", "Hello")
            assert result is True


class TestWeChatWorkIntegration:
    """Test WeChat Work integration"""

    @pytest.mark.asyncio
    async def test_authenticate(self):
        """Test WeChat Work authentication"""
        wechat = WeChatWorkIntegration("test_corp_id", "test_corp_secret")

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "errcode": 0,
                "access_token": "test_token",
                "expires_in": 7200,
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await wechat.authenticate()
            assert result is True
            assert wechat.access_token == "test_token"

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending message via WeChat Work"""
        wechat = WeChatWorkIntegration("test_corp_id", "test_corp_secret")
        wechat.access_token = "test_token"
        wechat.token_expire_time = float("inf")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"errcode": 0})
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await wechat.send_message("user123", "Hello")
            assert result is True


class TestEnterpriseIMManager:
    """Test Enterprise IM Manager"""

    @pytest.mark.asyncio
    async def test_register_platform(self):
        """Test registering a platform"""
        manager = EnterpriseIMManager()
        platform = MagicMock(spec=EnterpriseIMPlatform)

        manager.register_platform("test", platform)
        assert manager.get_platform("test") == platform

    @pytest.mark.asyncio
    async def test_list_platforms(self):
        """Test listing platforms"""
        manager = EnterpriseIMManager()
        platform1 = MagicMock(spec=EnterpriseIMPlatform)
        platform2 = MagicMock(spec=EnterpriseIMPlatform)

        manager.register_platform("platform1", platform1)
        manager.register_platform("platform2", platform2)

        platforms = manager.list_platforms()
        assert len(platforms) == 2
        assert "platform1" in platforms
        assert "platform2" in platforms

    @pytest.mark.asyncio
    async def test_send_message_to_all(self):
        """Test sending message to all platforms"""
        manager = EnterpriseIMManager()
        platform1 = AsyncMock(spec=EnterpriseIMPlatform)
        platform2 = AsyncMock(spec=EnterpriseIMPlatform)

        platform1.send_message = AsyncMock(return_value=True)
        platform2.send_message = AsyncMock(return_value=True)

        manager.register_platform("platform1", platform1)
        manager.register_platform("platform2", platform2)

        user_mappings = {
            "platform1": "user1",
            "platform2": "user2",
        }

        results = await manager.send_message_to_all(user_mappings, "Hello")
        assert results["platform1"] is True
        assert results["platform2"] is True


class TestMessageRouter:
    """Test Message Router"""

    @pytest.mark.asyncio
    async def test_route_message(self):
        """Test routing a message"""
        manager = MagicMock(spec=EnterpriseIMManager)
        manager.send_message_to_platform = AsyncMock(return_value=True)
        manager.list_platforms = MagicMock(return_value=["platform1"])

        router = MessageRouter(manager)
        results = await router.route_message("user123", "Hello", ["platform1"])

        assert results["platform1"] is True

    @pytest.mark.asyncio
    async def test_delivery_stats(self):
        """Test delivery statistics"""
        manager = MagicMock(spec=EnterpriseIMManager)
        router = MessageRouter(manager)

        # Log some deliveries
        router._log_delivery("platform1", "user1", "message", True)
        router._log_delivery("platform1", "user2", "message", False)

        stats = router.get_delivery_stats()
        assert stats["total"] == 2
        assert stats["success"] == 1
        assert stats["failed"] == 1
        assert stats["success_rate"] == 0.5


class TestUserMapping:
    """Test User Mapping"""

    @pytest.mark.asyncio
    async def test_map_user(self):
        """Test mapping a user"""
        mapping = UserMapping()
        success = await mapping.map_user("internal_user1", "platform1", "platform_user1")

        assert success is True
        platform_id = await mapping.get_platform_user_id("internal_user1", "platform1")
        assert platform_id == "platform_user1"

    @pytest.mark.asyncio
    async def test_reverse_mapping(self):
        """Test reverse mapping"""
        mapping = UserMapping()
        await mapping.map_user("internal_user1", "platform1", "platform_user1")

        internal_id = await mapping.get_internal_user_id("platform1", "platform_user1")
        assert internal_id == "internal_user1"

    @pytest.mark.asyncio
    async def test_unmap_user(self):
        """Test unmapping a user"""
        mapping = UserMapping()
        await mapping.map_user("internal_user1", "platform1", "platform_user1")

        success = await mapping.unmap_user("internal_user1", "platform1")
        assert success is True

        platform_id = await mapping.get_platform_user_id("internal_user1", "platform1")
        assert platform_id is None

    @pytest.mark.asyncio
    async def test_bulk_sync_users(self):
        """Test bulk syncing users"""
        mapping = UserMapping()
        users = [
            {"userid": "user1", "name": "User 1"},
            {"userid": "user2", "name": "User 2"},
        ]

        results = await mapping.bulk_sync_users("platform1", users)
        assert results["total"] == 2
        assert results["success"] == 2

    @pytest.mark.asyncio
    async def test_search_user(self):
        """Test searching for users"""
        mapping = UserMapping()
        await mapping.map_user("internal_user1", "platform1", "platform_user1")
        await mapping.map_user("internal_user2", "platform1", "platform_user2")

        results = await mapping.search_user("user1")
        assert len(results) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
