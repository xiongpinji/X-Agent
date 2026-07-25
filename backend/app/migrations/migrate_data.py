"""
数据迁移脚本 - 从旧存储导出到新存储
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from backend.app.core.database import init_db_manager
from backend.app.models.api_key_store import get_api_key_store
from backend.app.models.approval_store import get_approval_store
from backend.app.models.user_store import get_user_store

logger = logging.getLogger(__name__)


class DataMigrator:
    """数据迁移器"""

    def __init__(
        self,
        database_url: str,
        redis_url: str | None = None,
    ):
        self.database_url = database_url
        self.redis_url = redis_url
        self.stats = {
            "users_migrated": 0,
            "api_keys_migrated": 0,
            "approvals_migrated": 0,
            "errors": 0,
        }

    async def initialize(self) -> None:
        """初始化数据库连接"""
        await init_db_manager(
            self.database_url,
            self.redis_url,
        )
        logger.info("数据库连接已初始化")

    async def migrate_users_from_json(self, json_file: Path) -> int:
        """从JSON文件迁移用户"""
        if not json_file.exists():
            logger.warning(f"用户文件不存在: {json_file}")
            return 0

        try:
            with open(json_file) as f:
                data = json.load(f)

            user_store = get_user_store()
            count = 0

            for user_data in data.get("users", []):
                try:
                    await user_store.create_user(
                        user_id=user_data.get("user_id"),
                        email=user_data.get("email"),
                        password_hash=user_data.get("password_hash"),
                        tenant_id=user_data.get("tenant_id", "default"),
                        full_name=user_data.get("full_name"),
                        role=user_data.get("role", "user"),
                        metadata=user_data.get("metadata"),
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"用户迁移失败: {user_data.get('user_id')} - {e}")
                    self.stats["errors"] += 1

            self.stats["users_migrated"] = count
            logger.info(f"用户迁移完成: {count}个")
            return count

        except Exception as e:
            logger.error(f"用户迁移失败: {e}")
            self.stats["errors"] += 1
            return 0

    async def migrate_api_keys_from_json(self, json_file: Path) -> int:
        """从JSON文件迁移API密钥"""
        if not json_file.exists():
            logger.warning(f"API密钥文件不存在: {json_file}")
            return 0

        try:
            with open(json_file) as f:
                data = json.load(f)

            api_key_store = get_api_key_store()
            count = 0

            for key_data in data.get("api_keys", []):
                try:
                    await api_key_store.create_api_key(
                        key_id=key_data.get("key_id"),
                        key_prefix=key_data.get("key_prefix"),
                        key_hash=key_data.get("key_hash"),
                        user_id=key_data.get("user_id"),
                        tenant_id=key_data.get("tenant_id", "default"),
                        name=key_data.get("name"),
                        role=key_data.get("role", "developer"),
                        scopes=key_data.get("scopes", []),
                        expires_at=key_data.get("expires_at"),
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"API密钥迁移失败: {key_data.get('key_id')} - {e}")
                    self.stats["errors"] += 1

            self.stats["api_keys_migrated"] = count
            logger.info(f"API密钥迁移完成: {count}个")
            return count

        except Exception as e:
            logger.error(f"API密钥迁移失败: {e}")
            self.stats["errors"] += 1
            return 0

    async def migrate_approvals_from_json(self, json_file: Path) -> int:
        """从JSON文件迁移审批"""
        if not json_file.exists():
            logger.warning(f"审批文件不存在: {json_file}")
            return 0

        try:
            with open(json_file) as f:
                data = json.load(f)

            approval_store = get_approval_store()
            count = 0

            for approval_data in data.get("approvals", []):
                try:
                    await approval_store.create_approval(
                        approval_id=approval_data.get("approval_id"),
                        tenant_id=approval_data.get("tenant_id", "default"),
                        user_id=approval_data.get("user_id"),
                        request_id=approval_data.get("request_id"),
                        action=approval_data.get("action"),
                        resource_type=approval_data.get("resource_type"),
                        resource_id=approval_data.get("resource_id"),
                        details=approval_data.get("details", {}),
                        expires_at=approval_data.get("expires_at"),
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"审批迁移失败: {approval_data.get('approval_id')} - {e}")
                    self.stats["errors"] += 1

            self.stats["approvals_migrated"] = count
            logger.info(f"审批迁移完成: {count}个")
            return count

        except Exception as e:
            logger.error(f"审批迁移失败: {e}")
            self.stats["errors"] += 1
            return 0

    async def verify_migration(self) -> dict:
        """验证迁移数据一致性"""
        user_store = get_user_store()
        api_key_store = get_api_key_store()
        approval_store = get_approval_store()

        verification = {
            "users_count": await user_store.count_users(),
            "api_keys_count": len(await api_key_store.list_api_keys("", "")),
            "approvals_count": len(await approval_store.list_pending_approvals("")),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info(f"迁移验证完成: {verification}")
        return verification

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats.copy()


async def run_migration(
    database_url: str,
    redis_url: str | None = None,
    data_dir: Path = Path("data"),
) -> dict:
    """运行完整的数据迁移"""
    migrator = DataMigrator(database_url, redis_url)
    await migrator.initialize()

    # 迁移用户
    await migrator.migrate_users_from_json(data_dir / "users.json")

    # 迁移API密钥
    await migrator.migrate_api_keys_from_json(data_dir / "api_keys.json")

    # 迁移审批
    await migrator.migrate_approvals_from_json(data_dir / "approvals.json")

    # 验证迁移
    verification = await migrator.verify_migration()

    stats = migrator.get_stats()
    stats["verification"] = verification

    logger.info(f"迁移完成: {stats}")
    return stats


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("用法: python migrate_data.py <database_url> [redis_url] [data_dir]")
        sys.exit(1)

    database_url = sys.argv[1]
    redis_url = sys.argv[2] if len(sys.argv) > 2 else None
    data_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("data")

    result = asyncio.run(run_migration(database_url, redis_url, data_dir))
    print(json.dumps(result, indent=2))
