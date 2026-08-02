"""Authentication module.

This package provides a clean, layered authentication implementation
consisting of password hashing/verification, token management, session
handling, and a high-level facade tying it all together.

Modules
-------
- ``security`` : password hashing and verification utilities.
- ``tokens``   : access/refresh token creation and validation.
- ``sessions`` : authenticated-session model and store.
- ``service``  : high-level ``AuthService`` facade.
"""

from .security import PasswordHasher, hash_password, verify_password
from .service import AuthConfig, AuthenticationError, AuthService
from .sessions import Session, SessionStore
from .tokens import TokenManager, TokenPair, TokenPayload

__all__ = [
    "AuthConfig",
    "AuthService",
    "AuthenticationError",
    "PasswordHasher",
    "Session",
    "SessionStore",
    "TokenManager",
    "TokenPair",
    "TokenPayload",
    "hash_password",
    "verify_password",
]
