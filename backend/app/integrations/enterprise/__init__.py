"""Enterprise IM Platform Integration Module"""

from .base import EnterpriseIMPlatform
from .manager import EnterpriseIMManager
from .message_router import MessageRouter
from .user_mapping import UserMapping

__all__ = [
    "EnterpriseIMManager",
    "EnterpriseIMPlatform",
    "MessageRouter",
    "UserMapping",
]
