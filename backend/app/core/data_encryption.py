"""Data encryption utilities for protecting sensitive information.

SECURITY: Implements AES-256-GCM encryption for sensitive data fields.
"""

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode


class DataEncryptor:
    """Encrypts and decrypts sensitive data using AES-256-GCM."""

    # Version markers for ciphertext format
    _VERSION_V2 = b"\x02"  # New format with random salt
    _LEGACY_SALT = b"xagent_salt_v1"  # Fixed salt for v1 decryption only (backward compatibility)

    def __init__(self, master_key: str):
        """Initialize encryptor with master key.

        Args:
            master_key: Master encryption key (minimum 32 characters)

        Raises:
            ValueError: If master key is too short
        """
        if len(master_key) < 32:
            raise ValueError("Master key must be at least 32 characters")

        # Derive a 256-bit key from master key using PBKDF2
        self.master_key = master_key.encode()

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive encryption key from master key using provided salt.

        Args:
            salt: Salt for PBKDF2 derivation (16 bytes recommended)

        Returns:
            32-byte encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(self.master_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using AES-256-GCM with random salt (v2 format).

        Args:
            plaintext: Text to encrypt

        Returns:
            Base64-encoded ciphertext with version marker, random salt, nonce and tag

        Raises:
            api_error: If encryption fails
        """
        try:
            # Generate random salt for this encryption (16 bytes)
            salt = os.urandom(16)
            key = self._derive_key(salt)
            nonce = os.urandom(12)  # 96-bit nonce for GCM
            cipher = AESGCM(key)

            ciphertext = cipher.encrypt(nonce, plaintext.encode(), None)

            # v2 format: [version_byte][salt][nonce][ciphertext+tag]
            # GCM includes the tag in the ciphertext
            combined = self._VERSION_V2 + salt + nonce + ciphertext

            # Return base64-encoded result
            return base64.b64encode(combined).decode()

        except Exception as e:
            raise api_error(
                500,
                ErrorCode.VALIDATION_ERROR,
                f"Encryption failed: {e!s}",
            )

    def decrypt(self, ciphertext_b64: str) -> str:
        """Decrypt ciphertext using AES-256-GCM, supporting both v1 and v2 formats.

        Backward compatible: detects format version and uses appropriate salt.
        - v2 format: [version_byte=0x02][salt(16)][nonce(12)][ciphertext+tag]
        - v1 format (legacy): [nonce(12)][ciphertext+tag] (uses fixed salt)

        Args:
            ciphertext_b64: Base64-encoded ciphertext with nonce and tag

        Returns:
            Decrypted plaintext

        Raises:
            api_error: If decryption fails
        """
        try:
            # Decode base64
            combined = base64.b64decode(ciphertext_b64)

            # Detect format version
            if len(combined) > 0 and combined[0:1] == self._VERSION_V2:
                # v2 format: [version_byte][salt(16)][nonce(12)][ciphertext+tag]
                if len(combined) < 1 + 16 + 12:
                    raise ValueError("Invalid v2 ciphertext length")

                salt = combined[1:17]
                nonce = combined[17:29]
                ciphertext = combined[29:]
                key = self._derive_key(salt)
            else:
                # v1 format (legacy): [nonce(12)][ciphertext+tag] with fixed salt
                if len(combined) < 12:
                    raise ValueError("Invalid v1 ciphertext length")

                nonce = combined[:12]
                ciphertext = combined[12:]
                key = self._derive_key(self._LEGACY_SALT)

            cipher = AESGCM(key)
            plaintext = cipher.decrypt(nonce, ciphertext, None)

            return plaintext.decode()

        except Exception as e:
            raise api_error(
                400,
                ErrorCode.VALIDATION_ERROR,
                f"Decryption failed: {e!s}",
            )


class SensitiveFieldEncryptor:
    """Encrypts specific sensitive fields in data structures."""

    def __init__(self, encryptor: DataEncryptor, fields_to_encrypt: list[str]):
        """Initialize field encryptor.

        Args:
            encryptor: DataEncryptor instance
            fields_to_encrypt: List of field names to encrypt
        """
        self.encryptor = encryptor
        self.fields_to_encrypt = set(fields_to_encrypt)

    def encrypt_dict(self, data: dict) -> dict:
        """Encrypt sensitive fields in dictionary.

        Args:
            data: Dictionary to encrypt

        Returns:
            Dictionary with sensitive fields encrypted
        """
        result = data.copy()

        for field in self.fields_to_encrypt:
            if result.get(field):
                result[field] = self.encryptor.encrypt(str(result[field]))

        return result

    def decrypt_dict(self, data: dict) -> dict:
        """Decrypt sensitive fields in dictionary.

        Args:
            data: Dictionary to decrypt

        Returns:
            Dictionary with sensitive fields decrypted
        """
        result = data.copy()

        for field in self.fields_to_encrypt:
            if result.get(field):
                try:
                    result[field] = self.encryptor.decrypt(result[field])
                except Exception:
                    # If decryption fails, leave field as-is
                    pass

        return result


# Global encryptor instance
_encryptor: DataEncryptor | None = None


def get_encryptor(master_key: str | None = None) -> DataEncryptor:
    """Get or create global encryptor instance.

    Args:
        master_key: Optional master encryption key

    Returns:
        DataEncryptor instance
    """
    global _encryptor

    if _encryptor is None:
        if not master_key:
            from backend.app.settings import get_settings
            settings = get_settings()
            master_key = settings.encryption_key

        _encryptor = DataEncryptor(master_key)

    return _encryptor


# Sensitive fields that should be encrypted
SENSITIVE_FIELDS = {
    "api_key": ["key_hash"],
    "user": ["password_hash"],
    "oauth_token": ["access_token", "refresh_token"],
    "webhook": ["secret"],
}
