"""Backup encryption and compression utilities."""

import gzip
import hashlib
import io
import logging
from abc import ABC, abstractmethod
from typing import Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import os

logger = logging.getLogger(__name__)


class CompressionProvider(ABC):
    """Abstract base class for compression providers."""

    @abstractmethod
    def compress(self, data: bytes) -> bytes:
        """Compress data."""
        pass

    @abstractmethod
    def decompress(self, data: bytes) -> bytes:
        """Decompress data."""
        pass


class GzipCompression(CompressionProvider):
    """Gzip compression provider."""

    def __init__(self, compression_level: int = 9):
        self.compression_level = compression_level

    def compress(self, data: bytes) -> bytes:
        """Compress data using gzip."""
        try:
            buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=self.compression_level) as gz:
                gz.write(data)
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"Gzip compression failed: {e}")
            raise

    def decompress(self, data: bytes) -> bytes:
        """Decompress gzip data."""
        try:
            buffer = io.BytesIO(data)
            with gzip.GzipFile(fileobj=buffer, mode='rb') as gz:
                return gz.read()
        except Exception as e:
            logger.error(f"Gzip decompression failed: {e}")
            raise


class EncryptionProvider(ABC):
    """Abstract base class for encryption providers."""

    @abstractmethod
    def encrypt(self, data: bytes, key: bytes) -> tuple[bytes, bytes]:
        """Encrypt data. Returns (ciphertext, iv)."""
        pass

    @abstractmethod
    def decrypt(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Decrypt data."""
        pass


class AES256GCMEncryption(EncryptionProvider):
    """AES-256-GCM encryption provider."""

    def __init__(self):
        self.backend = default_backend()

    def encrypt(self, data: bytes, key: bytes) -> tuple[bytes, bytes]:
        """Encrypt data using AES-256-GCM."""
        try:
            # Generate random IV (96 bits for GCM)
            iv = os.urandom(12)

            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=self.backend
            )
            encryptor = cipher.encryptor()

            # Encrypt data
            ciphertext = encryptor.update(data) + encryptor.finalize()

            # Get authentication tag
            tag = encryptor.tag

            # Combine ciphertext and tag
            encrypted_data = ciphertext + tag

            logger.debug(f"Data encrypted successfully (size: {len(data)} -> {len(encrypted_data)})")
            return encrypted_data, iv
        except Exception as e:
            logger.error(f"AES-256-GCM encryption failed: {e}")
            raise

    def decrypt(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Decrypt data using AES-256-GCM."""
        try:
            # Extract tag (last 16 bytes)
            tag = ciphertext[-16:]
            encrypted_data = ciphertext[:-16]

            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, tag),
                backend=self.backend
            )
            decryptor = cipher.decryptor()

            # Decrypt data
            plaintext = decryptor.update(encrypted_data) + decryptor.finalize()

            logger.debug(f"Data decrypted successfully (size: {len(ciphertext)} -> {len(plaintext)})")
            return plaintext
        except Exception as e:
            logger.error(f"AES-256-GCM decryption failed: {e}")
            raise


class BackupEncryption:
    """Backup encryption manager."""

    def __init__(self, master_key: Optional[bytes] = None):
        self.encryption = AES256GCMEncryption()
        self.master_key = master_key or os.urandom(32)  # 256-bit key

    def derive_key(self, password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """Derive encryption key from password using PBKDF2."""
        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode())
        return key, salt

    def encrypt_backup(
        self,
        data: bytes,
        key: Optional[bytes] = None,
    ) -> tuple[bytes, bytes]:
        """Encrypt backup data."""
        encryption_key = key or self.master_key
        return self.encryption.encrypt(data, encryption_key)

    def decrypt_backup(
        self,
        ciphertext: bytes,
        iv: bytes,
        key: Optional[bytes] = None,
    ) -> bytes:
        """Decrypt backup data."""
        decryption_key = key or self.master_key
        return self.encryption.decrypt(ciphertext, decryption_key, iv)


class BackupCompression:
    """Backup compression manager."""

    def __init__(self, compression_level: int = 9):
        self.compression = GzipCompression(compression_level)

    def compress_backup(self, data: bytes) -> bytes:
        """Compress backup data."""
        try:
            compressed = self.compression.compress(data)
            ratio = len(compressed) / len(data) if data else 0
            logger.info(
                f"Backup compressed: {len(data)} -> {len(compressed)} bytes "
                f"(ratio: {ratio:.2%})"
            )
            return compressed
        except Exception as e:
            logger.error(f"Backup compression failed: {e}")
            raise

    def decompress_backup(self, data: bytes) -> bytes:
        """Decompress backup data."""
        try:
            decompressed = self.compression.decompress(data)
            logger.info(
                f"Backup decompressed: {len(data)} -> {len(decompressed)} bytes"
            )
            return decompressed
        except Exception as e:
            logger.error(f"Backup decompression failed: {e}")
            raise


class BackupIntegrity:
    """Backup integrity verification."""

    @staticmethod
    def calculate_checksum(data: bytes, algorithm: str = "SHA-256") -> str:
        """Calculate data checksum."""
        if algorithm == "SHA-256":
            return hashlib.sha256(data).hexdigest()
        elif algorithm == "SHA-512":
            return hashlib.sha512(data).hexdigest()
        elif algorithm == "MD5":
            return hashlib.md5(data).hexdigest()
        else:
            raise ValueError(f"Unsupported checksum algorithm: {algorithm}")

    @staticmethod
    def verify_checksum(
        data: bytes,
        expected_checksum: str,
        algorithm: str = "SHA-256",
    ) -> bool:
        """Verify data checksum."""
        calculated = BackupIntegrity.calculate_checksum(data, algorithm)
        return calculated == expected_checksum


class BackupProcessor:
    """Unified backup processor combining compression and encryption."""

    def __init__(
        self,
        encryption_key: Optional[bytes] = None,
        compression_level: int = 9,
        enable_encryption: bool = True,
        enable_compression: bool = True,
    ):
        self.encryption = BackupEncryption(encryption_key)
        self.compression = BackupCompression(compression_level)
        self.integrity = BackupIntegrity()
        self.enable_encryption = enable_encryption
        self.enable_compression = enable_compression

    def process_backup(self, data: bytes) -> tuple[bytes, dict]:
        """Process backup data (compress and encrypt)."""
        try:
            original_size = len(data)
            processed_data = data

            # Compress
            if self.enable_compression:
                processed_data = self.compression.compress_backup(processed_data)

            # Encrypt
            if self.enable_encryption:
                processed_data, iv = self.encryption.encrypt_backup(processed_data)
            else:
                iv = b""

            # Calculate checksum
            checksum = self.integrity.calculate_checksum(data)

            metadata = {
                "original_size": original_size,
                "processed_size": len(processed_data),
                "compression_ratio": len(processed_data) / original_size if original_size > 0 else 0,
                "checksum": checksum,
                "iv": iv.hex() if iv else "",
                "encrypted": self.enable_encryption,
                "compressed": self.enable_compression,
            }

            logger.info(f"Backup processed: {metadata}")
            return processed_data, metadata
        except Exception as e:
            logger.error(f"Backup processing failed: {e}")
            raise

    def restore_backup(
        self,
        processed_data: bytes,
        iv: Optional[bytes] = None,
    ) -> bytes:
        """Restore backup data (decrypt and decompress)."""
        try:
            restored_data = processed_data

            # Decrypt
            if self.enable_encryption and iv:
                restored_data = self.encryption.decrypt_backup(restored_data, iv)

            # Decompress
            if self.enable_compression:
                restored_data = self.compression.decompress_backup(restored_data)

            logger.info(f"Backup restored: {len(processed_data)} -> {len(restored_data)} bytes")
            return restored_data
        except Exception as e:
            logger.error(f"Backup restoration failed: {e}")
            raise
