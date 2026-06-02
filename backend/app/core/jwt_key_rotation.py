"""JWT密钥轮换机制 - 支持多密钥验证和定期轮换。

SECURITY: 实现OWASP密钥管理最佳实践
- 支持多个活跃密钥并存
- 定期自动轮换密钥
- 安全的密钥存储和加载
- 完整的审计日志
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class JWTKeyRecord(BaseModel):
    """JWT密钥记录"""
    key_id: str = Field(default_factory=lambda: str(uuid4()))
    key_material: str  # Base64编码的密钥材料
    algorithm: str = "HS256"  # 支持的算法
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rotated_at: datetime | None = None
    expires_at: datetime | None = None  # 密钥过期时间
    is_active: bool = True  # 是否为活跃密钥
    is_primary: bool = False  # 是否为主密钥（用于签名）
    rotation_reason: str | None = None  # 轮换原因


class JWTKeyRotationConfig(BaseModel):
    """密钥轮换配置"""
    rotation_interval_days: int = 90  # 轮换间隔（天）
    key_validity_days: int = 180  # 密钥有效期（天）
    max_active_keys: int = 3  # 最多保留的活跃密钥数
    auto_rotate: bool = True  # 是否自动轮换


class JWTKeyRotationStore:
    """JWT密钥轮换存储和管理"""

    def __init__(
        self,
        storage_path: str | Path | None = None,
        config: JWTKeyRotationConfig | None = None,
    ) -> None:
        self._records: dict[str, JWTKeyRecord] = {}
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        self._config = config or JWTKeyRotationConfig()
        if self._storage_path:
            self._load_from_disk()
        else:
            # 初始化时创建第一个密钥
            self._create_initial_key()

    def _create_initial_key(self) -> JWTKeyRecord:
        """创建初始密钥"""
        key_material = token_urlsafe(32)
        record = JWTKeyRecord(
            key_material=key_material,
            is_active=True,
            is_primary=True,
        )
        with self._lock:
            self._records[record.key_id] = record
            self._persist()
        logger.info(f"Created initial JWT key: {record.key_id}")
        return record

    def get_primary_key(self) -> JWTKeyRecord:
        """获取主密钥（用于签名）"""
        with self._lock:
            for record in self._records.values():
                if record.is_primary and record.is_active:
                    if record.expires_at and datetime.now(UTC) > record.expires_at:
                        continue
                    return record
        # 如果没有主密钥，创建一个
        return self._create_initial_key()

    def get_active_keys(self) -> list[JWTKeyRecord]:
        """获取所有活跃密钥（用于验证）"""
        with self._lock:
            active_keys = []
            for record in self._records.values():
                if not record.is_active:
                    continue
                # 检查是否过期
                if record.expires_at and datetime.now(UTC) > record.expires_at:
                    continue
                active_keys.append(record)
            return sorted(active_keys, key=lambda r: r.created_at, reverse=True)

    def rotate_key(self, reason: str = "Scheduled rotation") -> JWTKeyRecord:
        """轮换密钥 - 创建新密钥并将旧密钥标记为非主密钥"""
        with self._lock:
            # 获取当前主密钥
            old_primary = None
            for record in self._records.values():
                if record.is_primary and record.is_active:
                    old_primary = record
                    break

            # 创建新密钥
            key_material = token_urlsafe(32)
            new_record = JWTKeyRecord(
                key_material=key_material,
                is_active=True,
                is_primary=True,
                rotation_reason=reason,
            )

            # 更新旧主密钥
            if old_primary:
                old_primary.is_primary = False
                old_primary.rotated_at = datetime.now(UTC)
                # 设置过期时间
                old_primary.expires_at = datetime.now(UTC) + timedelta(
                    days=self._config.key_validity_days
                )
                self._records[old_primary.key_id] = old_primary

            # 保存新密钥
            self._records[new_record.key_id] = new_record

            # 清理过期的非活跃密钥
            self._cleanup_expired_keys()

            self._persist()
            logger.info(
                f"Rotated JWT key. Old: {old_primary.key_id if old_primary else 'None'}, "
                f"New: {new_record.key_id}, Reason: {reason}"
            )
            return new_record

    def revoke_key(self, key_id: str, reason: str = "Manual revocation") -> bool:
        """撤销密钥"""
        with self._lock:
            record = self._records.get(key_id)
            if record is None:
                return False

            record.is_active = False
            record.rotation_reason = reason
            self._records[key_id] = record
            self._persist()
            logger.warning(f"Revoked JWT key: {key_id}, Reason: {reason}")
            return True

    def get_key_by_id(self, key_id: str) -> JWTKeyRecord | None:
        """根据ID获取密钥"""
        with self._lock:
            return self._records.get(key_id)

    def list_keys(self, include_inactive: bool = False) -> list[JWTKeyRecord]:
        """列出所有密钥"""
        with self._lock:
            keys = list(self._records.values())
            if not include_inactive:
                keys = [k for k in keys if k.is_active]
            return sorted(keys, key=lambda k: k.created_at, reverse=True)

    def should_rotate(self) -> bool:
        """检查是否应该轮换密钥"""
        if not self._config.auto_rotate:
            return False

        primary_key = self.get_primary_key()
        if not primary_key:
            return False

        # 检查是否超过轮换间隔
        age = datetime.now(UTC) - primary_key.created_at
        return age > timedelta(days=self._config.rotation_interval_days)

    def _cleanup_expired_keys(self) -> None:
        """清理过期的密钥"""
        now = datetime.now(UTC)
        expired_keys = []

        for key_id, record in self._records.items():
            if not record.is_active and record.expires_at and now > record.expires_at:
                expired_keys.append(key_id)

        for key_id in expired_keys:
            del self._records[key_id]
            logger.info(f"Cleaned up expired key: {key_id}")

    def _load_from_disk(self) -> None:
        """从磁盘加载密钥"""
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            with self._storage_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            for item in payload:
                record = JWTKeyRecord.model_validate(item)
                self._records[record.key_id] = record
            logger.info(f"Loaded {len(self._records)} JWT keys from disk")
        except Exception as e:
            logger.error(f"Failed to load JWT keys from disk: {e}")

    def _persist(self) -> None:
        """保存密钥到磁盘"""
        if self._storage_path is None:
            return
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = [record.model_dump(mode="json") for record in self.list_keys(include_inactive=True)]
            self._storage_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to persist JWT keys: {e}")


# 全局实例
_jwt_key_store: JWTKeyRotationStore | None = None


def get_jwt_key_store(
    storage_path: str | Path | None = None,
    config: JWTKeyRotationConfig | None = None,
) -> JWTKeyRotationStore:
    """获取JWT密钥轮换存储实例"""
    global _jwt_key_store
    if _jwt_key_store is None:
        _jwt_key_store = JWTKeyRotationStore(storage_path=storage_path, config=config)
    return _jwt_key_store
