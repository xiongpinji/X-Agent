"""Message Router for Enterprise IM Platforms"""

from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from enum import Enum

from .base import EnterpriseIMPlatform, MessageType
from .manager import EnterpriseIMManager


class EventType(str, Enum):
    """Event types for notifications"""
    MESSAGE_RECEIVED = "message_received"
    APPROVAL_CREATED = "approval_created"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    CONTACT_UPDATED = "contact_updated"


class MessageRouter:
    """Route messages to appropriate platforms and users"""

    def __init__(self, manager: EnterpriseIMManager):
        self.manager = manager
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.message_queue: List[Dict[str, Any]] = []
        self.delivery_log: List[Dict[str, Any]] = []

    def register_event_handler(self, event_type: EventType, handler: Callable):
        """Register an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def unregister_event_handler(self, event_type: EventType, handler: Callable):
        """Unregister an event handler"""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].remove(handler)

    async def route_message(
        self,
        user_id: str,
        message: str,
        platforms: List[str] = None,
        msg_type: MessageType = MessageType.TEXT,
    ) -> Dict[str, bool]:
        """Route a message to user on specified platforms"""
        if platforms is None:
            platforms = self.manager.list_platforms()

        results = {}
        for platform_name in platforms:
            try:
                success = await self.manager.send_message_to_platform(
                    platform_name, user_id, message, msg_type
                )
                results[platform_name] = success
                self._log_delivery(platform_name, user_id, message, success)
            except Exception as e:
                print(f"Failed to route message to {platform_name}: {e}")
                results[platform_name] = False
                self._log_delivery(platform_name, user_id, message, False, str(e))

        return results

    async def route_card(
        self,
        user_id: str,
        card: Dict[str, Any],
        platforms: List[str] = None,
    ) -> Dict[str, bool]:
        """Route a card message to user on specified platforms"""
        if platforms is None:
            platforms = self.manager.list_platforms()

        results = {}
        for platform_name in platforms:
            try:
                success = await self.manager.send_card_to_platform(
                    platform_name, user_id, card
                )
                results[platform_name] = success
                self._log_delivery(platform_name, user_id, str(card), success)
            except Exception as e:
                print(f"Failed to route card to {platform_name}: {e}")
                results[platform_name] = False
                self._log_delivery(platform_name, user_id, str(card), False, str(e))

        return results

    async def broadcast_message(
        self,
        message: str,
        platforms: List[str] = None,
        filter_func: Optional[Callable] = None,
        msg_type: MessageType = MessageType.TEXT,
    ) -> Dict[str, Dict[str, bool]]:
        """Broadcast a message to all users on specified platforms"""
        if platforms is None:
            platforms = self.manager.list_platforms()

        results = {}
        for platform_name in platforms:
            platform = self.manager.get_platform(platform_name)
            if not platform:
                continue

            try:
                # Sync contacts first
                contacts = await platform.sync_contacts()
                platform_results = {}

                for contact in contacts:
                    user_id = contact.get("userid") or contact.get("id") or contact.get("open_id")
                    if not user_id:
                        continue

                    # Apply filter if provided
                    if filter_func and not filter_func(contact):
                        continue

                    success = await self.manager.send_message_to_platform(
                        platform_name, user_id, message, msg_type
                    )
                    platform_results[user_id] = success
                    self._log_delivery(platform_name, user_id, message, success)

                results[platform_name] = platform_results
            except Exception as e:
                print(f"Failed to broadcast on {platform_name}: {e}")
                results[platform_name] = {}

        return results

    async def send_notification(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        platforms: List[str] = None,
    ) -> Dict[str, bool]:
        """Send a notification based on event type"""
        if platforms is None:
            platforms = self.manager.list_platforms()

        # Build notification message based on event type
        message = self._build_notification_message(event_type, data)
        if not message:
            return {}

        # Route to specified user or broadcast
        if "user_id" in data:
            return await self.route_message(
                data["user_id"], message, platforms, MessageType.MARKDOWN
            )
        else:
            results = await self.broadcast_message(
                message, platforms, msg_type=MessageType.MARKDOWN
            )
            return {k: all(v.values()) if v else False for k, v in results.items()}

    def _build_notification_message(self, event_type: EventType, data: Dict[str, Any]) -> str:
        """Build notification message based on event type"""
        if event_type == EventType.MESSAGE_RECEIVED:
            return f"# 新消息\n\n{data.get('content', '')}"
        elif event_type == EventType.APPROVAL_CREATED:
            return f"# 审批创建\n\n审批ID: {data.get('approval_id')}\n申请人: {data.get('applicant')}"
        elif event_type == EventType.APPROVAL_APPROVED:
            return f"# 审批通过\n\n审批ID: {data.get('approval_id')}\n审批人: {data.get('approver')}"
        elif event_type == EventType.APPROVAL_REJECTED:
            return f"# 审批拒绝\n\n审批ID: {data.get('approval_id')}\n审批人: {data.get('approver')}\n原因: {data.get('reason', '无')}"
        elif event_type == EventType.USER_JOINED:
            return f"# 用户加入\n\n用户: {data.get('user_name')}"
        elif event_type == EventType.USER_LEFT:
            return f"# 用户离开\n\n用户: {data.get('user_name')}"
        elif event_type == EventType.CONTACT_UPDATED:
            return f"# 通讯录更新\n\n更新内容: {data.get('update_content', '')}"
        return ""

    async def trigger_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
    ):
        """Trigger an event and call registered handlers"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    if callable(handler):
                        result = handler(data)
                        if hasattr(result, "__await__"):
                            await result
                except Exception as e:
                    print(f"Event handler failed: {e}")

    def _log_delivery(
        self,
        platform: str,
        user_id: str,
        message: str,
        success: bool,
        error: str = None,
    ):
        """Log message delivery"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "user_id": user_id,
            "message_preview": message[:100],
            "success": success,
            "error": error,
        }
        self.delivery_log.append(log_entry)

        # Keep only last 1000 entries
        if len(self.delivery_log) > 1000:
            self.delivery_log = self.delivery_log[-1000:]

    def get_delivery_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get delivery log"""
        return self.delivery_log[-limit:]

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get delivery statistics"""
        if not self.delivery_log:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "success_rate": 0.0,
            }

        total = len(self.delivery_log)
        success = sum(1 for log in self.delivery_log if log["success"])
        failed = total - success

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": success / total if total > 0 else 0.0,
        }

    def get_platform_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics per platform"""
        stats = {}
        for platform_name in self.manager.list_platforms():
            platform_logs = [log for log in self.delivery_log if log["platform"] == platform_name]
            if platform_logs:
                total = len(platform_logs)
                success = sum(1 for log in platform_logs if log["success"])
                stats[platform_name] = {
                    "total": total,
                    "success": success,
                    "failed": total - success,
                    "success_rate": success / total if total > 0 else 0.0,
                }
        return stats
