"""Unit tests for the :class:`UserService`.

This module verifies the behaviour of the user service, including user
creation, retrieval by id, and listing of all users.
"""

from __future__ import annotations

import unittest

from models.user import User
from services.user_service import UserService


class TestUserService(unittest.TestCase):
    """Test cases for :class:`UserService`."""

    def setUp(self) -> None:
        """Create a fresh service instance before each test."""
        self.service = UserService()

    def test_create_user(self) -> None:
        """Creating a user stores it and assigns a unique id."""
        user = self.service.create_user(name="Alice", email="alice@example.com")

        self.assertIsInstance(user, User)
        self.assertEqual(user.id, 1)
        self.assertEqual(user.name, "Alice")
        self.assertEqual(user.email, "alice@example.com")
        self.assertIsNotNone(user.created_at)

    def test_create_user_increments_id(self) -> None:
        """Each created user receives a monotonically increasing id."""
        first = self.service.create_user("A", "a@example.com")
        second = self.service.create_user("B", "b@example.com")

        self.assertEqual(first.id, 1)
        self.assertEqual(second.id, 2)
        self.assertNotEqual(first.id, second.id)

    def test_get_user_returns_existing_user(self) -> None:
        """get_user returns the user matching the given id."""
        created = self.service.create_user("Alice", "alice@example.com")

        result = self.service.get_user(created.id)

        self.assertIs(result, created)

    def test_get_user_returns_none_for_missing(self) -> None:
        """get_user returns None when the id does not exist."""
        result = self.service.get_user(999)

        self.assertIsNone(result)

    def test_list_users_empty(self) -> None:
        """An empty service lists no users."""
        self.assertEqual(self.service.list_users(), [])

    def test_list_users_returns_all(self) -> None:
        """list_users returns every created user."""
        self.service.create_user("Alice", "alice@example.com")
        self.service.create_user("Bob", "bob@example.com")

        users = self.service.list_users()

        self.assertEqual(len(users), 2)
        names = {u.name for u in users}
        self.assertEqual(names, {"Alice", "Bob"})


if __name__ == "__main__":
    unittest.main()
