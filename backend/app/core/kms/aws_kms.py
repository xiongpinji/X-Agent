"""AWS KMS 实现 — 基于 boto3 的密钥管理.

使用 AWS KMS 进行加密/解密/轮换。密钥由 AWS 托管,
支持自动年度轮换和手动轮换。

前置条件:
  - boto3 已安装: pip install boto3
  - AWS 凭证已配置 (环境变量/IAM Role/credentials file)
  - KMS Key 已创建 (或使用现有 Key ID)

环境变量:
  XAGENT_KMS_AWS_KEY_ID: KMS Key ID 或 ARN
  XAGENT_KMS_AWS_REGION: AWS 区域 (默认 us-east-1)
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY: AWS 凭证
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.app.core.kms.base import (
    DecryptResult,
    EncryptResult,
    KeyMetadata,
    KMSBackend,
    KMSProvider,
)

logger = logging.getLogger(__name__)


class AWSKMS(KMSProvider):
    """AWS KMS 提供者.

    使用 AWS KMS Encrypt/Decrypt API 进行对称加密。
    AWS KMS 自动管理密钥版本, 密文中嵌入了 Key ID 和版本信息。

    注意: AWS KMS 单次加密最大 4KB, 大数据应使用信封加密
    (见 envelope.py), 用 KMS 加密 DEK, 用 DEK 加密数据。
    """

    def __init__(self, key_id: str, region: str = "us-east-1",
                 key_prefix: str = "xagent"):
        self._key_id = key_id
        self._region = region
        self._key_prefix = key_prefix
        self._client = None

    def _get_client(self):
        """延迟创建 boto3 KMS client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("kms", region_name=self._region)
            except ImportError:
                raise RuntimeError(
                    "boto3 is required for AWS KMS. Install: pip install boto3"
                )
        return self._client

    def encrypt(self, plaintext: bytes, key_name: str = "master") -> EncryptResult:
        """通过 AWS KMS 加密 (最大 4KB)."""
        client = self._get_client()
        response = client.encrypt(
            KeyId=self._key_id,
            Plaintext=plaintext,
            EncryptionContext={"purpose": f"{self._key_prefix}-{key_name}"},
        )
        # AWS KMS 密文已包含 Key ID 和版本信息
        ciphertext = response["CiphertextBlob"]
        key_version = self._extract_version(response.get("KeyId", self._key_id))

        return EncryptResult(
            ciphertext=ciphertext,
            key_id=response.get("KeyId", self._key_id),
            key_version=key_version,
        )

    def decrypt(self, ciphertext: bytes, key_name: str = "master",
                key_version: int | None = None, nonce: bytes = b"",
                tag: bytes = b"") -> DecryptResult:
        """通过 AWS KMS 解密."""
        client = self._get_client()
        response = client.decrypt(
            CiphertextBlob=ciphertext,
            EncryptionContext={"purpose": f"{self._key_prefix}-{key_name}"},
        )
        plaintext = response["Plaintext"]
        key_id = response.get("KeyId", self._key_id)
        key_ver = self._extract_version(key_id)

        return DecryptResult(
            plaintext=plaintext,
            key_id=key_id,
            key_version=key_ver,
        )

    def rotate_key(self, key_name: str = "master") -> KeyMetadata:
        """启用 AWS KMS 自动轮换 (年度).

        AWS KMS 不支持即时手动轮换对称密钥,
        而是启用自动年度轮换。调用此方法确保轮换已启用。
        """
        client = self._get_client()
        # 启用自动轮换
        client.enable_key_rotation(KeyId=self._key_id)
        logger.info("AWS KMS auto-rotation enabled for key: %s", self._key_id)
        return self.get_key_metadata(key_name)

    def get_key_metadata(self, key_name: str = "master") -> KeyMetadata:
        """获取 AWS KMS 密钥元数据."""
        client = self._get_client()
        response = client.describe_key(KeyId=self._key_id)
        key_meta = response["KeyMetadata"]

        # 获取轮换状态
        try:
            rotation = client.get_key_rotation_status(KeyId=self._key_id)
            rotation.get("KeyRotationEnabled", False)
        except Exception:
            pass

        status = "active"
        if key_meta.get("KeyState") == "Disabled":
            status = "disabled"
        elif key_meta.get("KeyState") == "PendingDeletion":
            status = "pending_deletion"

        return KeyMetadata(
            key_id=key_meta.get("Arn", self._key_id),
            version=self._extract_version(key_meta.get("Arn", "")),
            backend=KMSBackend.AWS_KMS,
            created_at=key_meta.get(
                "CreationDate", datetime.now(UTC)
            ),
            status=status,
        )

    def list_key_versions(self, key_name: str = "master") -> list[KeyMetadata]:
        """AWS KMS 不暴露历史版本列表, 返回当前密钥信息."""
        return [self.get_key_metadata(key_name)]

    def health_check(self) -> bool:
        """检查 AWS KMS 连通性."""
        try:
            client = self._get_client()
            client.describe_key(KeyId=self._key_id)
            return True
        except Exception:
            return False

    @staticmethod
    def _extract_version(key_arn: str) -> int:
        """从 ARN 或 Key ID 提取版本 (AWS 不直接暴露版本号, 返回 1)."""
        # AWS KMS 对称密钥的版本管理是内部的, 不暴露版本号
        return 1
