"""信封加密 (Envelope Encryption) 实现.

核心思想:
- KEK (Key Encryption Key): 由 KMS 管理的主密钥, 用于加密/解密 DEK
- DEK (Data Encryption Key): 随机生成的数据密钥, 用于加密/解密实际数据

流程:
  加密: KMS.generate_dek() → DEK 加密数据 → KMS.encrypt(DEK) → 存储 (encrypted_dek + ciphertext)
  解密: KMS.decrypt(encrypted_dek) → DEK → DEK 解密数据

优势:
- 大数据无需经过 KMS (AWS KMS 限制 4KB)
- 轮换 KEK 只需重新加密 DEK, 无需重新加密所有数据
- DEK 可缓存, 减少 KMS 调用次数
"""

from __future__ import annotations

import logging
import os
import struct
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.app.core.kms.base import KMSProvider

logger = logging.getLogger(__name__)

# 信封格式版本
_ENVELOPE_VERSION = 1
# DEK 大小 (AES-256)
_DEK_SIZE = 32
# GCM nonce 大小
_NONCE_SIZE = 12


@dataclass
class EnvelopeResult:
    """信封加密结果."""

    # 序列化后的完整信封 (可直接存储)
    envelope: bytes
    # 各部分 (调试用)
    encrypted_dek: bytes
    nonce: bytes
    ciphertext: bytes
    key_version: int


@dataclass
class DecryptedEnvelope:
    """信封解密结果."""

    plaintext: bytes
    key_version: int


class EnvelopeEncryption:
    """信封加密引擎.

    使用 KMS 保护 DEK, 使用 DEK (AES-256-GCM) 加密实际数据。
    """

    def __init__(self, kms: KMSProvider, key_name: str = "master"):
        self._kms = kms
        self._key_name = key_name

    def encrypt(self, plaintext: bytes, associated_data: bytes | None = None) -> EnvelopeResult:
        """信封加密.

        Args:
            plaintext: 待加密数据
            associated_data: AAD (附加认证数据, 可选)

        Returns:
            EnvelopeResult 包含序列化信封
        """
        # 1. 生成随机 DEK
        dek = os.urandom(_DEK_SIZE)

        try:
            # 2. 用 DEK 加密数据 (AES-256-GCM)
            nonce = os.urandom(_NONCE_SIZE)
            aesgcm = AESGCM(dek)
            ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

            # 3. 用 KMS 加密 DEK
            kms_result = self._kms.encrypt(dek, key_name=self._key_name)

            # 4. 序列化为信封格式
            envelope = self._serialize(
                encrypted_dek=kms_result.ciphertext,
                nonce=nonce,
                ciphertext=ciphertext,
                key_version=kms_result.key_version,
                aad=associated_data,
            )

            return EnvelopeResult(
                envelope=envelope,
                encrypted_dek=kms_result.ciphertext,
                nonce=nonce,
                ciphertext=ciphertext,
                key_version=kms_result.key_version,
            )
        finally:
            # 清除内存中的 DEK
            dek = b"\x00" * _DEK_SIZE

    def decrypt(self, envelope: bytes, associated_data: bytes | None = None) -> DecryptedEnvelope:
        """信封解密.

        Args:
            envelope: 序列化的信封字节
            associated_data: AAD (必须与加密时一致)

        Returns:
            DecryptedEnvelope 包含明文
        """
        # 1. 反序列化信封
        parts = self._deserialize(envelope)

        # 2. 用 KMS 解密 DEK
        kms_result = self._kms.decrypt(
            parts["encrypted_dek"],
            key_name=self._key_name,
            key_version=parts["key_version"],
        )
        dek = kms_result.plaintext

        try:
            # 3. 用 DEK 解密数据
            aesgcm = AESGCM(dek)
            plaintext = aesgcm.decrypt(parts["nonce"], parts["ciphertext"], associated_data)

            return DecryptedEnvelope(
                plaintext=plaintext,
                key_version=parts["key_version"],
            )
        finally:
            dek = b"\x00" * _DEK_SIZE

    def re_encrypt_dek(self, envelope: bytes) -> bytes:
        """重新加密 DEK (密钥轮换后使用).

        不重新加密数据, 只用新版 KEK 重新加密 DEK。
        这是信封加密的核心优势: 轮换成本 O(1) 而非 O(n)。

        Args:
            envelope: 原始信封

        Returns:
            新信封 (DEK 用新版 KEK 加密)
        """
        parts = self._deserialize(envelope)

        # 解密 DEK (用旧版 KEK)
        kms_result = self._kms.decrypt(
            parts["encrypted_dek"],
            key_name=self._key_name,
            key_version=parts["key_version"],
        )
        dek = kms_result.plaintext

        try:
            # 用新版 KEK 重新加密 DEK
            new_kms_result = self._kms.encrypt(dek, key_name=self._key_name)

            # 重新序列化
            return self._serialize(
                encrypted_dek=new_kms_result.ciphertext,
                nonce=parts["nonce"],
                ciphertext=parts["ciphertext"],
                key_version=new_kms_result.key_version,
                aad=parts.get("aad"),
            )
        finally:
            dek = b"\x00" * _DEK_SIZE

    @staticmethod
    def _serialize(encrypted_dek: bytes, nonce: bytes, ciphertext: bytes,
                   key_version: int, aad: bytes | None = None) -> bytes:
        """序列化信封格式.

        格式:
          [1B version][4B key_version][4B dek_len][dek][12B nonce][4B ct_len][ct][4B aad_len][aad]
        """
        aad_bytes = aad or b""
        parts = [
            struct.pack("B", _ENVELOPE_VERSION),
            struct.pack(">I", key_version),
            struct.pack(">I", len(encrypted_dek)),
            encrypted_dek,
            nonce,
            struct.pack(">I", len(ciphertext)),
            ciphertext,
            struct.pack(">I", len(aad_bytes)),
            aad_bytes,
        ]
        return b"".join(parts)

    @staticmethod
    def _deserialize(envelope: bytes) -> dict:
        """反序列化信封格式."""
        offset = 0

        version = struct.unpack_from("B", envelope, offset)[0]
        offset += 1
        if version != _ENVELOPE_VERSION:
            raise ValueError(f"Unsupported envelope version: {version}")

        key_version = struct.unpack_from(">I", envelope, offset)[0]
        offset += 4

        dek_len = struct.unpack_from(">I", envelope, offset)[0]
        offset += 4
        encrypted_dek = envelope[offset:offset + dek_len]
        offset += dek_len

        nonce = envelope[offset:offset + _NONCE_SIZE]
        offset += _NONCE_SIZE

        ct_len = struct.unpack_from(">I", envelope, offset)[0]
        offset += 4
        ciphertext = envelope[offset:offset + ct_len]
        offset += ct_len

        aad_len = struct.unpack_from(">I", envelope, offset)[0]
        offset += 4
        aad = envelope[offset:offset + aad_len] if aad_len > 0 else None

        return {
            "version": version,
            "key_version": key_version,
            "encrypted_dek": encrypted_dek,
            "nonce": nonce,
            "ciphertext": ciphertext,
            "aad": aad,
        }
