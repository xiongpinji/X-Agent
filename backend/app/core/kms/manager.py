"""KMS Manager — 统一密钥管理入口.

提供:
- 工厂方法: 根据配置创建对应后端 (Local/Vault/AWS)
- 信封加密快捷接口
- 自动密钥轮换检查
- 单例访问 (get_kms_manager)
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta

from backend.app.core.kms.base import (
    DecryptResult,
    EncryptResult,
    KeyMetadata,
    KMSBackend,
    KMSConfig,
    KMSProvider,
)
from backend.app.core.kms.envelope import EnvelopeEncryption

logger = logging.getLogger(__name__)

# 全局单例
_kms_manager: KMSManager | None = None
_kms_lock = threading.Lock()


class KMSManager:
    """KMS 统一管理器.

    封装 KMSProvider + EnvelopeEncryption, 提供:
    - encrypt/decrypt: 信封加密 (推荐, 无大小限制)
    - encrypt_raw/decrypt_raw: 直接 KMS 加密 (≤4KB)
    - rotate_if_needed: 自动轮换检查
    - rotate: 手动轮换
    """

    def __init__(self, config: KMSConfig | None = None):
        self._config = config or KMSConfig()
        self._provider = self._create_provider(self._config)
        self._envelope = EnvelopeEncryption(self._provider)
        self._last_rotation_check: datetime | None = None

    @staticmethod
    def _create_provider(config: KMSConfig) -> KMSProvider:
        """根据配置创建 KMS 后端."""
        if config.backend == KMSBackend.LOCAL:
            from backend.app.core.kms.local import LocalKMS
            return LocalKMS(
                key_dir=config.local_key_path,
                key_prefix=config.key_prefix,
            )
        elif config.backend == KMSBackend.VAULT:
            from backend.app.core.kms.vault import VaultKMS
            return VaultKMS(
                addr=config.vault_addr,
                token=config.vault_token,
                mount=config.vault_mount,
                key_prefix=config.key_prefix,
            )
        elif config.backend == KMSBackend.AWS_KMS:
            from backend.app.core.kms.aws_kms import AWSKMS
            return AWSKMS(
                key_id=config.aws_key_id,
                region=config.aws_region,
                key_prefix=config.key_prefix,
            )
        else:
            raise ValueError(f"Unsupported KMS backend: {config.backend}")

    @property
    def provider(self) -> KMSProvider:
        """底层 KMS 提供者."""
        return self._provider

    @property
    def backend(self) -> KMSBackend:
        """当前后端类型."""
        return self._config.backend

    # ─── 信封加密 (推荐) ───────────────────────────────────────────

    def encrypt(self, plaintext: bytes, associated_data: bytes | None = None) -> bytes:
        """信封加密, 返回序列化信封字节."""
        result = self._envelope.encrypt(plaintext, associated_data)
        return result.envelope

    def decrypt(self, envelope: bytes, associated_data: bytes | None = None) -> bytes:
        """信封解密, 返回明文字节."""
        result = self._envelope.decrypt(envelope, associated_data)
        return result.plaintext

    def encrypt_str(self, plaintext: str, associated_data: str | None = None) -> bytes:
        """字符串信封加密."""
        aad = associated_data.encode() if associated_data else None
        return self.encrypt(plaintext.encode(), aad)

    def decrypt_str(self, envelope: bytes, associated_data: str | None = None) -> str:
        """字符串信封解密."""
        aad = associated_data.encode() if associated_data else None
        return self.decrypt(envelope, aad).decode()

    # ─── 直接 KMS 加密 (≤4KB) ─────────────────────────────────────

    def encrypt_raw(self, plaintext: bytes, key_name: str = "master") -> EncryptResult:
        """直接 KMS 加密 (适用于小数据/DEK)."""
        return self._provider.encrypt(plaintext, key_name)

    def decrypt_raw(self, ciphertext: bytes, key_name: str = "master",
                    key_version: int | None = None) -> DecryptResult:
        """直接 KMS 解密."""
        return self._provider.decrypt(ciphertext, key_name, key_version)

    # ─── 密钥轮换 ─────────────────────────────────────────────────

    def rotate(self, key_name: str = "master") -> KeyMetadata:
        """手动轮换密钥."""
        meta = self._provider.rotate_key(key_name)
        logger.info("Key rotated: %s v%d", meta.key_id, meta.version)
        return meta

    def rotate_if_needed(self, key_name: str = "master") -> KeyMetadata | None:
        """自动轮换检查: 超过 auto_rotate_days 则轮换.

        Returns:
            新密钥元数据 (如果发生了轮换), 否则 None
        """
        now = datetime.now(UTC)

        # 限流: 最多每小时检查一次
        if self._last_rotation_check and (now - self._last_rotation_check) < timedelta(hours=1):
            return None
        self._last_rotation_check = now

        if self._config.auto_rotate_days <= 0:
            return None  # 禁用自动轮换

        try:
            meta = self._provider.get_key_metadata(key_name)
            age = now - meta.created_at
            if age > timedelta(days=self._config.auto_rotate_days):
                logger.info(
                    "Key '%s' age %d days exceeds %d days, rotating...",
                    key_name, age.days, self._config.auto_rotate_days,
                )
                return self.rotate(key_name)
        except Exception as e:
            logger.warning("Auto-rotation check failed: %s", e)

        return None

    def re_encrypt_envelope(self, envelope: bytes) -> bytes:
        """轮换后重新加密信封中的 DEK."""
        return self._envelope.re_encrypt_dek(envelope)

    # ─── 元数据 ───────────────────────────────────────────────────

    def get_key_metadata(self, key_name: str = "master") -> KeyMetadata:
        return self._provider.get_key_metadata(key_name)

    def list_key_versions(self, key_name: str = "master") -> list[KeyMetadata]:
        return self._provider.list_key_versions(key_name)

    def health_check(self) -> bool:
        return self._provider.health_check()


def get_kms_manager(config: KMSConfig | None = None) -> KMSManager:
    """获取全局 KMS Manager 单例.

    首次调用时根据 settings 创建; 后续调用返回缓存实例。
    """
    global _kms_manager
    if _kms_manager is None:
        with _kms_lock:
            if _kms_manager is None:
                if config is None:
                    config = _config_from_settings()
                _kms_manager = KMSManager(config)
                logger.info("KMS Manager initialized (backend=%s)", config.backend.value)
    return _kms_manager


def _config_from_settings() -> KMSConfig:
    """从应用 settings 构建 KMSConfig."""
    try:
        from backend.app.settings import get_settings
        s = get_settings()
        backend_str = getattr(s, "kms_backend", "local")
        return KMSConfig(
            backend=KMSBackend(backend_str),
            local_key_path=getattr(s, "kms_local_key_path", ""),
            vault_addr=getattr(s, "kms_vault_addr", "http://127.0.0.1:8200"),
            vault_token=getattr(s, "kms_vault_token", ""),
            vault_mount=getattr(s, "kms_vault_mount", "transit"),
            vault_key_name=getattr(s, "kms_vault_key_name", "xagent-master"),
            aws_key_id=getattr(s, "kms_aws_key_id", ""),
            aws_region=getattr(s, "kms_aws_region", "us-east-1"),
            auto_rotate_days=getattr(s, "kms_auto_rotate_days", 90),
            key_prefix=getattr(s, "kms_key_prefix", "xagent"),
        )
    except Exception:
        # settings 不可用时使用默认配置
        return KMSConfig()
