"""Base class for Enterprise IM Platform Integration"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any


class MessageType(StrEnum):
    """Message types supported by enterprise IM platforms"""
    TEXT = "text"
    MARKDOWN = "markdown"
    CARD = "card"
    IMAGE = "image"
    FILE = "file"
    LINK = "link"


class ApprovalStatus(StrEnum):
    """Approval workflow status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class EnterpriseIMPlatform(ABC):
    """Abstract base class for enterprise IM platform integration"""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.is_connected = False
        self.last_sync_time: datetime | None = None

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the platform"""
        pass

    @abstractmethod
    async def send_message(self, user_id: str, message: str, msg_type: MessageType = MessageType.TEXT) -> bool:
        """Send a message to a user"""
        pass

    @abstractmethod
    async def send_card(self, user_id: str, card: dict[str, Any]) -> bool:
        """Send a card message to a user"""
        pass

    @abstractmethod
    async def send_markdown(self, user_id: str, title: str, text: str) -> bool:
        """Send a markdown message to a user"""
        pass

    @abstractmethod
    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """Get user information"""
        pass

    @abstractmethod
    async def sync_contacts(self) -> list[dict[str, Any]]:
        """Sync contacts from the platform"""
        pass

    @abstractmethod
    async def sync_departments(self) -> list[dict[str, Any]]:
        """Sync departments from the platform"""
        pass

    @abstractmethod
    async def create_approval(self, template_id: str, data: dict[str, Any]) -> str:
        """Create an approval workflow instance"""
        pass

    @abstractmethod
    async def get_approval_status(self, approval_id: str) -> dict[str, Any]:
        """Get approval workflow status"""
        pass

    @abstractmethod
    async def upload_file(self, file_path: str, file_type: str) -> str:
        """Upload a file to the platform"""
        pass

    @abstractmethod
    async def download_file(self, file_id: str) -> bytes:
        """Download a file from the platform"""
        pass

    async def health_check(self) -> bool:
        """Check platform connectivity"""
        try:
            await self.authenticate()
            return True
        except Exception:
            return False

    def get_platform_name(self) -> str:
        """Get platform name"""
        return self.platform_name

    def get_connection_status(self) -> dict[str, Any]:
        """Get connection status"""
        return {
            "platform": self.platform_name,
            "connected": self.is_connected,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
        }
