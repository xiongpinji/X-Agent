"""User domain model.

This module defines the :class:`User` dataclass representing a user of the
system. It contains the core identity and metadata fields for a user record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """A user of the system.

    Attributes:
        id: Unique identifier for the user.
        name: Display name of the user.
        email: Email address of the user.
        created_at: Timestamp indicating when the user was created.
    """

    id: int
    name: str
    email: str
    created_at: Optional[datetime] = field(default_factory=datetime.utcnow)
