"""KMS 抽象基类与数据模型."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

logger = logging.getLogger(__name__)


class KMSBackend(StrEnum):
    """KMS 后端类型."""

    LOCAL = "local"
    VAULT = "vault"
    AWS_KMS = "aws_kms"


@dataclass
class KMSConfig:
    """KMS 配置."""

    backend: KMSBackend = KMSBackend.LOCAL
    # Local
    local_key_path: str = ""
    # Vault
    vault_addr: str = "http://127.0.0.1:8200"
    vault_token: str = ""
    vault_mount: str = "transit"
    vault_key_name: str = "xagent-master"
    # AWS KMS
    aws_key_id: str = ""
    aws_region: str = "us-east-1"
    # 通用
    auto_rotate_days: int = 90
    key_prefix: str = "xagent"


@dataclass
class KeyMetadata:
    """密钥元数据."""

    key_id: str
    version: int
    backend: KMSBackend
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    rotated_at: datetime | None = None
    status: str = "active"  # active, rotated, disabled


@dataclass
class EncryptResult:
    """加密结果."""

    ciphertext: bytes
    key_id: str
    key_version: int
    nonce: bytes = b""
    tag: bytes = b""


@dataclass
class DecryptResult:
    """解密结果."""

    plaintext: bytes
    key_id: str
    key_version: int


class KMSProvider(ABC):
    """KMS 提供者抽象基类.

    所有后端 (Local/Vault/AWS) 实现此接口,
    提供统一的 encrypt/decrypt/rotate 操作.
    """

    @abstractmethod
    def encrypt(self, plaintext: bytes, key_name: str = "master") -> EncryptResult:
        """加密数据.

        Args:
            plaintext: 待加密的明文字节
            key_name: 密钥名称 (用于多密钥场景)

        Returns:
            EncryptResult 包含密文和密钥版本信息
        """
        ...

    @abstractmethod
    def decrypt(self, ciphertext: bytes, key_name: str = "master",
                key_version: int | None = None, nonce: bytes = b"",
                tag: bytes = b"") -> DecryptResult:
        """解密数据.

        Args:
            ciphertext: 密文字节
            key_name: 密钥名称
            key_version: 密钥版本 (None 表示使用最新版本)
            nonce: 加密时的 nonce/IV
            tag: GCM 认证标签

        Returns:
            DecryptResult 包含明文和密钥版本信息
        """
        ...

    @abstractmethod
    def rotate_key(self, key_name: str = "master") -> KeyMetadata:
        """轮换密钥.

        创建新版本密钥, 旧版本保留用于解密历史数据.

        Args:
            key_name: 密钥名称

        Returns:
            新密钥版本的元数据
        """
        ...

    @abstractmethod
    def get_key_metadata(self, key_name: str = "master") -> KeyMetadata:
        """获取密钥元数据.

        Args:
            key_name: 密钥名称

        Returns:
            当前密钥版本的元数据
        """
        ...

    @abstractmethod
    def list_key_versions(self, key_name: str = "master") -> list[KeyMetadata]:
        """列出密钥所有版本.

        Args:
            key_name: 密钥名称

        Returns:
            所有版本的元数据列表 (按版本降序)
        """
        ...

    def health_check(self) -> bool:
        """健康检查. 默认返回 True, 子类可覆盖."""
        return True
