"""Password hashing and verification utilities.

Uses PBKDF2-HMAC-SHA256 with a per-password random salt, provided by the
standard library ``hashlib`` and ``secrets`` modules, so no third-party
dependencies are required.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Final

#: Number of PBKDF2 iterations. 600k is a reasonable default for SHA-256.
PBKDF2_ITERATIONS: Final[int] = 600_000
#: Salt length in bytes.
SALT_BYTES: Final[int] = 16
#: Derived key length in bytes.
KEY_BYTES: Final[int] = 32
#: Algorithm identifier stored in the encoded hash.
_ALGORITHM: Final[str] = "pbkdf2_sha256"


def _encode(password_hash: str, salt: str, iterations: int) -> str:
    """Encode the storeable hash representation."""
    return f"{_ALGORITHM}${iterations}${salt}${password_hash}"


def _decode(encoded: str) -> tuple[str, int, str, str]:
    """Decode a stored hash into (algorithm, iterations, salt, digest)."""
    try:
        algorithm, iterations, salt, digest = encoded.split("$")
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("Malformed password hash") from exc
    if algorithm != _ALGORITHM:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    return algorithm, int(iterations), salt, digest


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256.

    Parameters
    ----------
    password:
        The plaintext password to hash.
    iterations:
        PBKDF2 iteration count (defaults to :data:`PBKDF2_ITERATIONS`).

    Returns
    -------
    str
        A self-describing hash string safe for storage.
    """
    if not isinstance(password, str):
        raise TypeError("password must be a str")
    if not password:
        raise ValueError("password must not be empty")

    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return _encode(digest, salt, iterations)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored hash.

    Uses ``hmac.compare_digest`` for constant-time comparison to avoid
    timing side channels.

    Parameters
    ----------
    password:
        The candidate plaintext password.
    stored_hash:
        A hash previously produced by :func:`hash_password`.

    Returns
    -------
    bool
        ``True`` if the password matches, ``False`` otherwise.
    """
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False
    try:
        _, iterations, salt, expected = _decode(stored_hash)
    except ValueError:
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return hmac.compare_digest(actual, expected)


class PasswordHasher:
    """Object-oriented wrapper around the module-level hashing functions.

    Useful for dependency injection and for customising iteration counts
    at construction time.
    """

    def __init__(self, iterations: int = PBKDF2_ITERATIONS) -> None:
        if iterations <= 0:
            raise ValueError("iterations must be positive")
        self.iterations = iterations

    def hash(self, password: str) -> str:
        """Hash a password with this instance's iteration count."""
        return hash_password(password, iterations=self.iterations)

    def verify(self, password: str, stored_hash: str) -> bool:
        """Verify a password against a stored hash."""
        return verify_password(password, stored_hash)
