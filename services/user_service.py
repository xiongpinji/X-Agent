"""User service layer.

This module provides the :class:`UserService`, which encapsulates the business
logic for creating, retrieving, and listing users backed by an in-memory store.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from models.user import User


class UserService:
    """Service for managing :class:`User` records.

    The service keeps users in an in-memory dictionary keyed by user id, and
    exposes methods to create, fetch by id, and list users.
    """

    def __init__(self) -> None:
        """Initialize an empty in-memory user store."""
        self._users: Dict[int, User] = {}
        self._next_id: int = 1

    def create_user(self, name: str, email: str) -> User:
        """Create and store a new user.

        Args:
            name: Display name of the user.
            email: Email address of the user.

        Returns:
            The newly created :class:`User`.
        """
        user = User(
            id=self._next_id,
            name=name,
            email=email,
            created_at=datetime.utcnow(),
        )
        self._users[user.id] = user
        self._next_id += 1
        return user

    def get_user(self, user_id: int) -> Optional[User]:
        """Fetch a user by its unique identifier.

        Args:
            user_id: The identifier of the user to retrieve.

        Returns:
            The matching :class:`User`, or ``None`` if no such user exists.
        """
        return self._users.get(user_id)

    def list_users(self) -> List[User]:
        """Return all stored users.

        Returns:
            A list of all :class:`User` records currently stored.
        """
        return list(self._users.values())
