"""Encryption module for sensitive configuration data."""

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Encryption operation error."""

    pass


class ConfigEncryption:
    """Handle encryption and decryption of sensitive configuration values."""

    def __init__(self, encryption_key: str):
        """Initialize encryption handler.

        Args:
            encryption_key: Encryption key (minimum 32 characters)

        Raises:
            EncryptionError: If key is invalid
        """
        if not encryption_key or len(encryption_key) < 32:
            raise EncryptionError("Encryption key must be at least 32 characters long")

        self.encryption_key = encryption_key
        self._cipher = self._create_cipher()

    def _create_cipher(self) -> Fernet:
        """Create Fernet cipher from encryption key.

        Returns:
            Fernet cipher instance
        """
        # Derive a proper key from the provided key using PBKDF2
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"xagent-config",  # Fixed salt for consistency
            iterations=100000,
        )
        key_bytes = kdf.derive(self.encryption_key.encode())
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        return Fernet(key_b64)

    def encrypt(self, value: str) -> str:
        """Encrypt a string value.

        Args:
            value: Value to encrypt

        Returns:
            Encrypted value (base64 encoded)

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            encrypted = self._cipher.encrypt(value.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, encrypted_value: str) -> str:
        """Decrypt an encrypted value.

        Args:
            encrypted_value: Encrypted value (base64 encoded)

        Returns:
            Decrypted value

        Raises:
            EncryptionError: If decryption fails
        """
        try:
            encrypted = base64.b64decode(encrypted_value.encode())
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode()
        except InvalidToken:
            raise EncryptionError("Decryption failed: Invalid token or corrupted data")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")

    def encrypt_dict(self, data: dict, keys_to_encrypt: list[str]) -> dict:
        """Encrypt specific keys in a dictionary.

        Args:
            data: Dictionary to encrypt
            keys_to_encrypt: List of keys to encrypt

        Returns:
            Dictionary with encrypted values

        Raises:
            EncryptionError: If encryption fails
        """
        encrypted_data = data.copy()
        for key in keys_to_encrypt:
            if key in encrypted_data and encrypted_data[key]:
                try:
                    encrypted_data[key] = self.encrypt(str(encrypted_data[key]))
                except Exception as e:
                    raise EncryptionError(f"Failed to encrypt key '{key}': {e}")
        return encrypted_data

    def decrypt_dict(self, data: dict, keys_to_decrypt: list[str]) -> dict:
        """Decrypt specific keys in a dictionary.

        Args:
            data: Dictionary to decrypt
            keys_to_decrypt: List of keys to decrypt

        Returns:
            Dictionary with decrypted values

        Raises:
            EncryptionError: If decryption fails
        """
        decrypted_data = data.copy()
        for key in keys_to_decrypt:
            if key in decrypted_data and decrypted_data[key]:
                try:
                    decrypted_data[key] = self.decrypt(str(decrypted_data[key]))
                except Exception as e:
                    raise EncryptionError(f"Failed to decrypt key '{key}': {e}")
        return decrypted_data


class EncryptedConfigValue:
    """Wrapper for encrypted configuration values."""

    def __init__(self, encrypted_value: str, encryption: ConfigEncryption):
        """Initialize encrypted value wrapper.

        Args:
            encrypted_value: Encrypted value
            encryption: ConfigEncryption instance
        """
        self.encrypted_value = encrypted_value
        self.encryption = encryption
        self._decrypted: Optional[str] = None

    @property
    def value(self) -> str:
        """Get decrypted value (lazy decryption).

        Returns:
            Decrypted value
        """
        if self._decrypted is None:
            self._decrypted = self.encryption.decrypt(self.encrypted_value)
        return self._decrypted

    def __str__(self) -> str:
        """Return decrypted value as string."""
        return self.value

    def __repr__(self) -> str:
        """Return representation (masked for security)."""
        return f"EncryptedConfigValue(***)"


def generate_encryption_key() -> str:
    """Generate a secure encryption key.

    Returns:
        Base64-encoded encryption key
    """
    key_bytes = os.urandom(32)
    return base64.b64encode(key_bytes).decode()


def load_encryption_key_from_env(env_var: str = "XAGENT_ENCRYPTION_KEY") -> Optional[str]:
    """Load encryption key from environment variable.

    Args:
        env_var: Environment variable name

    Returns:
        Encryption key or None if not set
    """
    return os.getenv(env_var)


def load_encryption_key_from_file(file_path: str) -> Optional[str]:
    """Load encryption key from file.

    Args:
        file_path: Path to file containing encryption key

    Returns:
        Encryption key or None if file doesn't exist

    Raises:
        EncryptionError: If file cannot be read
    """
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r") as f:
            return f.read().strip()
    except Exception as e:
        raise EncryptionError(f"Failed to load encryption key from file: {e}")
