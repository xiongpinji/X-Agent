"""HashiCorp Vault Transit 引擎 KMS 实现.

使用 Vault Transit secrets engine 进行加密/解密/轮换。
Vault 负责密钥存储和版本管理, 明文密钥永远不离开 Vault。

前置条件:
  - Vault 服务已启动且可访问
  - Transit 引擎已挂载: vault secrets enable transit
  - 密钥已创建: vault write -f transit/keys/xagent-master

环境变量:
  XAGENT_KMS_VAULT_ADDR: Vault 地址 (默认 http://127.0.0.1:8200)
  XAGENT_KMS_VAULT_TOKEN: Vault token
  XAGENT_KMS_VAULT_MOUNT: Transit 挂载路径 (默认 transit)
"""

from __future__ import annotations

import base64
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


class VaultKMS(KMSProvider):
    """HashiCorp Vault Transit KMS.

    通过 Vault HTTP API 操作 Transit 引擎:
    - POST /v1/{mount}/encrypt/{key} — 加密
    - POST /v1/{mount}/decrypt/{key} — 解密
    - POST /v1/{mount}/keys/{key}/rotate — 轮换
    - GET  /v1/{mount}/keys/{key} — 密钥元数据
    """

    def __init__(self, addr: str, token: str, mount: str = "transit",
                 key_prefix: str = "xagent"):
        self._addr = addr.rstrip("/")
        self._token = token
        self._mount = mount
        self._key_prefix = key_prefix
        self._session = None

    def _get_session(self):
        """延迟创建 HTTP session."""
        if self._session is None:
            try:
                import httpx
                self._session = httpx.Client(
                    base_url=self._addr,
                    headers={"X-Vault-Token": self._token},
                    timeout=10.0,
                )
            except ImportError:
                raise RuntimeError(
                    "httpx is required for Vault KMS. Install: pip install httpx"
                )
        return self._session

    def _vault_key_name(self, key_name: str) -> str:
        return f"{self._key_prefix}-{key_name}"

    def _ensure_key_exists(self, key_name: str) -> None:
        """确保 Vault 中密钥存在, 不存在则创建."""
        session = self._get_session()
        vault_key = self._vault_key_name(key_name)
        resp = session.get(f"/v1/{self._mount}/keys/{vault_key}")
        if resp.status_code == 404:
            # 创建 aes256-gcm96 类型密钥 (支持收敛加密和派生)
            create_resp = session.post(
                f"/v1/{self._mount}/keys/{vault_key}",
                json={"type": "aes256-gcm96", "auto_rotate_period": "2160h"},
            )
            if create_resp.status_code not in (200, 204):
                raise RuntimeError(
                    f"Failed to create Vault key '{vault_key}': {create_resp.text}"
                )
            logger.info("Created Vault transit key: %s", vault_key)

    def encrypt(self, plaintext: bytes, key_name: str = "master") -> EncryptResult:
        """通过 Vault Transit 加密."""
        self._ensure_key_exists(key_name)
        session = self._get_session()
        vault_key = self._vault_key_name(key_name)

        plaintext_b64 = base64.b64encode(plaintext).decode()
        resp = session.post(
            f"/v1/{self._mount}/encrypt/{vault_key}",
            json={"plaintext": plaintext_b64},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Vault encrypt failed: {resp.text}")

        data = resp.json()["data"]
        # Vault 返回格式: vault:v1:ciphertext...
        ciphertext_str = data["ciphertext"]
        # 解析版本号
        parts = ciphertext_str.split(":")
        version = int(parts[1].lstrip("v")) if len(parts) >= 3 else 1

        return EncryptResult(
            ciphertext=ciphertext_str.encode(),
            key_id=vault_key,
            key_version=version,
        )

    def decrypt(self, ciphertext: bytes, key_name: str = "master",
                key_version: int | None = None, nonce: bytes = b"",
                tag: bytes = b"") -> DecryptResult:
        """通过 Vault Transit 解密."""
        session = self._get_session()
        vault_key = self._vault_key_name(key_name)

        ciphertext_str = ciphertext.decode()
        resp = session.post(
            f"/v1/{self._mount}/decrypt/{vault_key}",
            json={"ciphertext": ciphertext_str},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Vault decrypt failed: {resp.text}")

        data = resp.json()["data"]
        plaintext = base64.b64decode(data["plaintext"])

        # 从密文格式解析版本
        parts = ciphertext_str.split(":")
        version = int(parts[1].lstrip("v")) if len(parts) >= 3 else 1

        return DecryptResult(
            plaintext=plaintext,
            key_id=vault_key,
            key_version=version,
        )

    def rotate_key(self, key_name: str = "master") -> KeyMetadata:
        """轮换 Vault Transit 密钥."""
        self._ensure_key_exists(key_name)
        session = self._get_session()
        vault_key = self._vault_key_name(key_name)

        resp = session.post(f"/v1/{self._mount}/keys/{vault_key}/rotate")
        if resp.status_code not in (200, 204):
            raise RuntimeError(f"Vault key rotation failed: {resp.text}")

        logger.info("Rotated Vault transit key: %s", vault_key)
        return self.get_key_metadata(key_name)

    def get_key_metadata(self, key_name: str = "master") -> KeyMetadata:
        """获取 Vault 密钥元数据."""
        session = self._get_session()
        vault_key = self._vault_key_name(key_name)

        resp = session.get(f"/v1/{self._mount}/keys/{vault_key}")
        if resp.status_code != 200:
            raise RuntimeError(f"Vault get key failed: {resp.text}")

        data = resp.json()["data"]
        return KeyMetadata(
            key_id=vault_key,
            version=data.get("latest_version", 1),
            backend=KMSBackend.VAULT,
            created_at=datetime.now(UTC),
            status="active",
        )

    def list_key_versions(self, key_name: str = "master") -> list[KeyMetadata]:
        """列出 Vault 密钥版本 (Vault 不暴露所有版本详情, 返回最新版本)."""
        meta = self.get_key_metadata(key_name)
        # Vault Transit 不直接暴露历史版本列表, 返回当前版本
        return [meta]

    def health_check(self) -> bool:
        """检查 Vault 连通性."""
        try:
            session = self._get_session()
            resp = session.get("/v1/sys/health")
            return resp.status_code in (200, 429, 472, 473, 501, 503)
        except Exception:
            return False

    def close(self):
        """关闭 HTTP session."""
        if self._session:
            self._session.close()
            self._session = None
