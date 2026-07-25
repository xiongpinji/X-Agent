"""Local KMS 实现 — 基于 Fernet 的本地密钥管理.

默认后端, 无需外部服务。密钥存储在本地文件系统中,
支持多版本密钥和轮换。生产环境建议使用 Vault 或 AWS KMS。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from backend.app.core.kms.base import (
    DecryptResult,
    EncryptResult,
    KeyMetadata,
    KMSBackend,
    KMSProvider,
)

logger = logging.getLogger(__name__)

# 默认密钥存储目录
_DEFAULT_KEY_DIR = ".xagent_runtime/keys"


class LocalKMS(KMSProvider):
    """本地 Fernet KMS.

    密钥以 JSON 文件存储, 每个密钥名对应一个文件:
      {key_dir}/{key_prefix}-{key_name}.json

    文件格式:
    {
      "key_name": "master",
      "current_version": 2,
      "versions": {
        "1": {"key": "<fernet_key_b64>", "created_at": "...", "status": "rotated"},
        "2": {"key": "<fernet_key_b64>", "created_at": "...", "status": "active"}
      }
    }
    """

    def __init__(self, key_dir: str = "", key_prefix: str = "xagent"):
        self._key_dir = Path(key_dir or _DEFAULT_KEY_DIR)
        self._key_prefix = key_prefix
        self._lock = threading.Lock()
        self._cache: dict[str, dict] = {}
        self._fernet_cache: dict[str, dict[int, Fernet]] = {}
        self._key_dir.mkdir(parents=True, exist_ok=True)

    def _key_file(self, key_name: str) -> Path:
        return self._key_dir / f"{self._key_prefix}-{key_name}.json"

    def _load_key_store(self, key_name: str) -> dict:
        """加载密钥存储, 不存在则初始化."""
        if key_name in self._cache:
            return self._cache[key_name]

        path = self._key_file(key_name)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                store = json.load(f)
        else:
            # 初始化: 生成第一个版本
            fernet_key = Fernet.generate_key().decode()
            store = {
                "key_name": key_name,
                "current_version": 1,
                "versions": {
                    "1": {
                        "key": fernet_key,
                        "created_at": datetime.now(UTC).isoformat(),
                        "status": "active",
                    }
                },
            }
            self._save_key_store(key_name, store)

        self._cache[key_name] = store
        return store

    def _save_key_store(self, key_name: str, store: dict) -> None:
        """持久化密钥存储."""
        path = self._key_file(key_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        # 写入时设置严格权限 (Unix); Windows 忽略
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)
        try:
            os.chmod(path, 0o600)
        except (OSError, NotImplementedError):
            pass  # Windows 不支持 chmod

    def _get_fernet(self, key_name: str, version: int) -> Fernet:
        """获取指定版本的 Fernet 实例 (带缓存)."""
        cache_key = key_name
        if cache_key not in self._fernet_cache:
            self._fernet_cache[cache_key] = {}

        if version not in self._fernet_cache[cache_key]:
            store = self._load_key_store(key_name)
            ver_str = str(version)
            if ver_str not in store["versions"]:
                raise ValueError(f"Key version {version} not found for '{key_name}'")
            key_b64 = store["versions"][ver_str]["key"].encode()
            self._fernet_cache[cache_key][version] = Fernet(key_b64)

        return self._fernet_cache[cache_key][version]

    def encrypt(self, plaintext: bytes, key_name: str = "master") -> EncryptResult:
        """使用当前版本密钥加密."""
        with self._lock:
            store = self._load_key_store(key_name)
            version = store["current_version"]
            fernet = self._get_fernet(key_name, version)
            ciphertext = fernet.encrypt(plaintext)
            return EncryptResult(
                ciphertext=ciphertext,
                key_id=f"{self._key_prefix}-{key_name}",
                key_version=version,
            )

    def decrypt(self, ciphertext: bytes, key_name: str = "master",
                key_version: int | None = None, nonce: bytes = b"",
                tag: bytes = b"") -> DecryptResult:
        """解密数据. 若未指定版本, 尝试所有版本 (从新到旧)."""
        with self._lock:
            store = self._load_key_store(key_name)

            if key_version is not None:
                fernet = self._get_fernet(key_name, key_version)
                plaintext = fernet.decrypt(ciphertext)
                return DecryptResult(
                    plaintext=plaintext,
                    key_id=f"{self._key_prefix}-{key_name}",
                    key_version=key_version,
                )

            # 未指定版本: 从当前版本向旧版本尝试
            versions = sorted(store["versions"].keys(), key=int, reverse=True)
            last_error = None
            for ver_str in versions:
                try:
                    ver = int(ver_str)
                    fernet = self._get_fernet(key_name, ver)
                    plaintext = fernet.decrypt(ciphertext)
                    return DecryptResult(
                        plaintext=plaintext,
                        key_id=f"{self._key_prefix}-{key_name}",
                        key_version=ver,
                    )
                except InvalidToken as e:
                    last_error = e
                    continue

            raise ValueError(
                f"Failed to decrypt with any key version for '{key_name}': {last_error}"
            )

    def rotate_key(self, key_name: str = "master") -> KeyMetadata:
        """轮换密钥: 生成新版本, 旧版本标记为 rotated."""
        with self._lock:
            store = self._load_key_store(key_name)
            old_version = store["current_version"]
            new_version = old_version + 1

            # 标记旧版本
            store["versions"][str(old_version)]["status"] = "rotated"

            # 生成新版本
            fernet_key = Fernet.generate_key().decode()
            now = datetime.now(UTC)
            store["versions"][str(new_version)] = {
                "key": fernet_key,
                "created_at": now.isoformat(),
                "status": "active",
            }
            store["current_version"] = new_version
            self._save_key_store(key_name, store)

            # 清除 Fernet 缓存
            self._fernet_cache.pop(key_name, None)

            logger.info(
                "Key '%s' rotated: v%d -> v%d", key_name, old_version, new_version
            )
            return KeyMetadata(
                key_id=f"{self._key_prefix}-{key_name}",
                version=new_version,
                backend=KMSBackend.LOCAL,
                created_at=now,
                rotated_at=now,
                status="active",
            )

    def get_key_metadata(self, key_name: str = "master") -> KeyMetadata:
        """获取当前密钥版本元数据."""
        store = self._load_key_store(key_name)
        version = store["current_version"]
        ver_data = store["versions"][str(version)]
        return KeyMetadata(
            key_id=f"{self._key_prefix}-{key_name}",
            version=version,
            backend=KMSBackend.LOCAL,
            created_at=datetime.fromisoformat(ver_data["created_at"]),
            status=ver_data["status"],
        )

    def list_key_versions(self, key_name: str = "master") -> list[KeyMetadata]:
        """列出所有密钥版本."""
        store = self._load_key_store(key_name)
        results = []
        for ver_str, ver_data in sorted(
            store["versions"].items(), key=lambda x: int(x[0]), reverse=True
        ):
            results.append(
                KeyMetadata(
                    key_id=f"{self._key_prefix}-{key_name}",
                    version=int(ver_str),
                    backend=KMSBackend.LOCAL,
                    created_at=datetime.fromisoformat(ver_data["created_at"]),
                    status=ver_data["status"],
                )
            )
        return results

    def health_check(self) -> bool:
        """检查密钥目录可写."""
        try:
            test_file = self._key_dir / ".health_check"
            test_file.write_text("ok")
            test_file.unlink()
            return True
        except OSError:
            return False
