"""
X-Agent Encryption Module

Handles AES-256-GCM encryption/decryption for sensitive data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from base64 import b64decode, b64encode
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionConfig:
    """Encryption configuration."""

    def __init__(
        self,
        algorithm: str = "AES-256-GCM",
        key_size: int = 32,  # 256 bits
        iv_size: int = 12,   # 96 bits for GCM
        salt_size: int = 16,
        tag_size: int = 16,
        iterations: int = 100000,
    ):
        """Initialize encryption configuration.

        Args:
            algorithm: Encryption algorithm
            key_size: Key size in bytes
            iv_size: IV size in bytes
            salt_size: Salt size in bytes
            tag_size: Authentication tag size in bytes
            iterations: PBKDF2 iterations
        """
        self.algorithm = algorithm
        self.key_size = key_size
        self.iv_size = iv_size
        self.salt_size = salt_size
        self.tag_size = tag_size
        self.iterations = iterations


class EncryptionManager:
    """Manages encryption/decryption operations."""

    def __init__(self, config: EncryptionConfig | None = None):
        """Initialize encryption manager.

        Args:
            config: Encryption configuration
        """
        self.config = config or EncryptionConfig()
        self._master_key: bytes | None = None
        self._key_cache: dict[int, bytes] = {}

    def set_master_key(self, key: bytes) -> None:
        """Set master encryption key.

        Args:
            key: Master key (should be 32 bytes for AES-256)
        """
        if len(key) != self.config.key_size:
            raise ValueError(
                f"Master key must be {self.config.key_size} bytes, "
                f"got {len(key)} bytes"
            )
        self._master_key = key
        self._key_cache.clear()

    def generate_master_key(self) -> bytes:
        """Generate a new master key.

        Returns:
            Generated master key
        """
        key = os.urandom(self.config.key_size)
        self.set_master_key(key)
        return key

    def derive_key_from_password(self, password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
        """Derive encryption key from password.

        Args:
            password: Password string
            salt: Salt (generated if not provided)

        Returns:
            Tuple of (derived_key, salt)
        """
        if salt is None:
            salt = os.urandom(self.config.salt_size)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.config.key_size,
            salt=salt,
            iterations=self.config.iterations,
            backend=default_backend(),
        )

        key = kdf.derive(password.encode())
        return key, salt

    def encrypt(
        self,
        plaintext: str | bytes | dict,
        associated_data: bytes | None = None,
    ) -> dict[str, str]:
        """Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt
            associated_data: Additional authenticated data (optional)

        Returns:
            Dictionary with encrypted_data, iv, salt, and tag
        """
        if self._master_key is None:
            raise ValueError("Master key not set. Call set_master_key() first.")

        # Convert plaintext to bytes
        if isinstance(plaintext, dict):
            plaintext_bytes = json.dumps(plaintext).encode()
        elif isinstance(plaintext, str):
            plaintext_bytes = plaintext.encode()
        else:
            plaintext_bytes = plaintext

        # Generate IV and salt
        iv = os.urandom(self.config.iv_size)
        salt = os.urandom(self.config.salt_size)

        # Create cipher
        cipher = AESGCM(self._master_key)

        # Encrypt
        ciphertext = cipher.encrypt(iv, plaintext_bytes, associated_data)

        # Return encrypted data with metadata
        return {
            "encrypted_data": b64encode(ciphertext).decode(),
            "iv": b64encode(iv).decode(),
            "salt": b64encode(salt).decode(),
            "algorithm": self.config.algorithm,
            "tag_size": self.config.tag_size,
        }

    def decrypt(
        self,
        encrypted_data: str,
        iv: str,
        salt: str,
        associated_data: bytes | None = None,
    ) -> bytes:
        """Decrypt data using AES-256-GCM.

        Args:
            encrypted_data: Encrypted data (base64)
            iv: Initialization vector (base64)
            salt: Salt (base64)
            associated_data: Additional authenticated data (optional)

        Returns:
            Decrypted data as bytes
        """
        if self._master_key is None:
            raise ValueError("Master key not set. Call set_master_key() first.")

        try:
            # Decode from base64
            ciphertext = b64decode(encrypted_data)
            iv_bytes = b64decode(iv)

            # Create cipher
            cipher = AESGCM(self._master_key)

            # Decrypt
            plaintext = cipher.decrypt(iv_bytes, ciphertext, associated_data)

            return plaintext

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError(f"Decryption failed: {e}")

    def decrypt_to_string(
        self,
        encrypted_data: str,
        iv: str,
        salt: str,
        associated_data: bytes | None = None,
    ) -> str:
        """Decrypt data to string.

        Args:
            encrypted_data: Encrypted data (base64)
            iv: Initialization vector (base64)
            salt: Salt (base64)
            associated_data: Additional authenticated data (optional)

        Returns:
            Decrypted string
        """
        plaintext = self.decrypt(encrypted_data, iv, salt, associated_data)
        return plaintext.decode()

    def decrypt_to_dict(
        self,
        encrypted_data: str,
        iv: str,
        salt: str,
        associated_data: bytes | None = None,
    ) -> dict:
        """Decrypt data to dictionary.

        Args:
            encrypted_data: Encrypted data (base64)
            iv: Initialization vector (base64)
            salt: Salt (base64)
            associated_data: Additional authenticated data (optional)

        Returns:
            Decrypted dictionary
        """
        plaintext = self.decrypt(encrypted_data, iv, salt, associated_data)
        return json.loads(plaintext.decode())

    def hash_data(self, data: str | bytes) -> str:
        """Hash data using SHA-256.

        Args:
            data: Data to hash

        Returns:
            Hex-encoded hash
        """
        if isinstance(data, str):
            data = data.encode()

        return hashlib.sha256(data).hexdigest()

    def verify_hash(self, data: str | bytes, hash_value: str) -> bool:
        """Verify data hash.

        Args:
            data: Data to verify
            hash_value: Expected hash value

        Returns:
            True if hash matches
        """
        return self.hash_data(data) == hash_value


class SensitiveDataClassifier:
    """Classifies data as sensitive or not."""

    # Sensitive data patterns
    SENSITIVE_PATTERNS = {
        "api_key": [
            "api_key", "apikey", "api-key",
            "secret", "token", "password",
            "credential", "auth", "bearer",
        ],
        "personal_info": [
            "email", "phone", "ssn", "passport",
            "credit_card", "bank_account",
        ],
        "code": [
            "code", "script", "function", "class",
        ],
    }

    @classmethod
    def is_sensitive(cls, data: Any, data_type: str | None = None) -> bool:
        """Check if data is sensitive.

        Args:
            data: Data to check
            data_type: Data type hint (optional)

        Returns:
            True if data is sensitive
        """
        if data_type:
            return data_type.lower() in cls.SENSITIVE_PATTERNS

        # Check content for sensitive patterns
        if isinstance(data, dict):
            for key in data:
                if cls._matches_pattern(key):
                    return True

        return bool(isinstance(data, str) and cls._matches_pattern(data))

    @classmethod
    def _matches_pattern(cls, text: str) -> bool:
        """Check if text matches sensitive patterns.

        Args:
            text: Text to check

        Returns:
            True if matches sensitive pattern
        """
        text_lower = text.lower()
        for patterns in cls.SENSITIVE_PATTERNS.values():
            for pattern in patterns:
                if pattern in text_lower:
                    return True
        return False

    @classmethod
    def classify(cls, data: Any, data_type: str | None = None) -> str:
        """Classify data sensitivity level.

        Args:
            data: Data to classify
            data_type: Data type hint (optional)

        Returns:
            Sensitivity level: 'public', 'internal', 'confidential', 'secret'
        """
        if cls.is_sensitive(data, data_type):
            return "secret"
        return "internal"


class EncryptedDataStore:
    """Stores and retrieves encrypted data."""

    def __init__(self, encryption_manager: EncryptionManager):
        """Initialize encrypted data store.

        Args:
            encryption_manager: Encryption manager instance
        """
        self.encryption_manager = encryption_manager

    def encrypt_and_store(
        self,
        data: Any,
        entity_type: str,
        entity_id: str,
        data_type: str,
    ) -> dict[str, Any]:
        """Encrypt and prepare data for storage.

        Args:
            data: Data to encrypt
            entity_type: Type of entity
            entity_id: Entity ID
            data_type: Type of data

        Returns:
            Dictionary with encrypted data and metadata
        """
        # Classify sensitivity
        sensitivity = SensitiveDataClassifier.classify(data, data_type)

        # Encrypt if sensitive
        if sensitivity == "secret":
            encrypted = self.encryption_manager.encrypt(data)
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "data_type": data_type,
                "sensitivity": sensitivity,
                "is_encrypted": True,
                "encrypted_data": encrypted["encrypted_data"],
                "iv": encrypted["iv"],
                "salt": encrypted["salt"],
                "algorithm": encrypted["algorithm"],
            }
        else:
            # Store unencrypted but marked
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "data_type": data_type,
                "sensitivity": sensitivity,
                "is_encrypted": False,
                "data": data,
            }

    def decrypt_and_retrieve(
        self,
        stored_data: dict[str, Any],
    ) -> Any:
        """Decrypt and retrieve data from storage.

        Args:
            stored_data: Stored data dictionary

        Returns:
            Decrypted data
        """
        if stored_data.get("is_encrypted"):
            return self.encryption_manager.decrypt_to_dict(
                stored_data["encrypted_data"],
                stored_data["iv"],
                stored_data["salt"],
            )
        else:
            return stored_data.get("data")


class KeyRotationManager:
    """Manages encryption key rotation."""

    def __init__(self, encryption_manager: EncryptionManager):
        """Initialize key rotation manager.

        Args:
            encryption_manager: Encryption manager instance
        """
        self.encryption_manager = encryption_manager
        self._key_versions: dict[int, bytes] = {}
        self._current_version = 1

    def add_key_version(self, version: int, key: bytes) -> None:
        """Add a key version.

        Args:
            version: Key version number
            key: Key material
        """
        if len(key) != self.encryption_manager.config.key_size:
            raise ValueError(
                f"Key must be {self.encryption_manager.config.key_size} bytes"
            )
        self._key_versions[version] = key

    def rotate_key(self, new_key: bytes) -> int:
        """Rotate to a new key.

        Args:
            new_key: New key material

        Returns:
            New key version
        """
        new_version = self._current_version + 1
        self.add_key_version(new_version, new_key)
        self._current_version = new_version
        self.encryption_manager.set_master_key(new_key)
        return new_version

    def get_key_version(self, version: int) -> bytes | None:
        """Get a specific key version.

        Args:
            version: Key version number

        Returns:
            Key material or None
        """
        return self._key_versions.get(version)

    def get_current_version(self) -> int:
        """Get current key version.

        Returns:
            Current key version
        """
        return self._current_version
