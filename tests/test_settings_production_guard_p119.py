"""P1-19 验证: settings 生产模式存储 fail-fast 守卫。

app_mode=production 时:
- database_url 为 sqlite                  -> 拒绝启动
- memory_backend 为 memory/jsonl          -> 拒绝启动
- trace_backend 为 memory                 -> 拒绝启动
- admin_store_backend 为 memory           -> 拒绝启动
全部外部化后允许启动; 非生产模式不受影响。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.settings import Settings, get_settings

# 满足既有生产校验的最小合规机密(>=32 字符, 含大写与数字)
_VALID_JWT = "ProdJWTSecret1234567890ABCDEFGHIJK"
_VALID_ENC = "ProdEncKey1234567890ABCDEFGHIJKLMN"

_POSTGRES_KWARGS = {
    "database_url": "postgresql+asyncpg://xagent:secret@db.internal:5432/xagent",
    "memory_backend": "postgres",
    "trace_backend": "postgres",
    "admin_store_backend": "postgres",
}


def _production_kwargs(**overrides):
    payload = {
        "app_mode": "production",
        "jwt_secret": _VALID_JWT,
        "encryption_key": _VALID_ENC,
        "audit_hmac_secret": "hmac-secret",
        "redis_url": "redis://localhost:6379/0",
    }
    payload.update(overrides)
    return payload


class TestProductionStorageFailFast:
    def test_sqlite_database_url_rejected(self):
        with pytest.raises(ValidationError, match="database_url 指向 sqlite"):
            Settings(**_production_kwargs(database_url="sqlite:///./data/xagent.db", memory_backend="postgres", trace_backend="postgres", admin_store_backend="postgres"))

    def test_memory_backend_variants_rejected(self):
        for backend in ("memory", "jsonl"):
            with pytest.raises(ValidationError, match="memory_backend"):
                Settings(**_production_kwargs(**{**_POSTGRES_KWARGS, "memory_backend": backend}))

    def test_memory_trace_backend_rejected(self):
        with pytest.raises(ValidationError, match="trace_backend"):
            Settings(**_production_kwargs(**{**_POSTGRES_KWARGS, "trace_backend": "memory"}))

    def test_memory_admin_store_backend_rejected(self):
        with pytest.raises(ValidationError, match="admin_store_backend"):
            Settings(**_production_kwargs(**{**_POSTGRES_KWARGS, "admin_store_backend": "memory"}))

    def test_all_violations_listed_together(self):
        """多项违规一次性全部列出(清晰错误信息, 避免逐条修复反复重启)。"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(**_production_kwargs(
                database_url="sqlite:///./data/xagent.db",
                memory_backend="memory",
                trace_backend="memory",
                admin_store_backend="memory",
            ))
        message = str(exc_info.value)
        assert "database_url 指向 sqlite" in message
        assert "memory_backend" in message
        assert "trace_backend" in message
        assert "admin_store_backend" in message
        assert "P1-19" in message

    def test_fully_externalized_production_accepted(self):
        settings = Settings(**_production_kwargs(**_POSTGRES_KWARGS))
        assert settings.app_mode == "production"
        assert settings.database_url.startswith("postgresql")

    def test_development_mode_unaffected(self):
        settings = Settings(app_mode="development")
        assert settings.app_mode == "development"
        assert settings.admin_store_backend == "file"

    def test_invalid_admin_store_backend_value_rejected(self):
        with pytest.raises(ValidationError, match="Invalid admin_store_backend"):
            Settings(admin_store_backend="cassandra")


class TestFailFastThroughEnvVars:
    """以环境变量切换实测(与生产部署的 12-factor 配置路径一致)。"""

    def test_env_driven_production_rejects_sqlite_defaults(self, monkeypatch):
        monkeypatch.setenv("XAGENT_APP_MODE", "production")
        monkeypatch.setenv("XAGENT_JWT_SECRET", _VALID_JWT)
        monkeypatch.setenv("XAGENT_ENCRYPTION_KEY", _VALID_ENC)
        monkeypatch.setenv("XAGENT_AUDIT_HMAC_SECRET", "hmac-secret")
        get_settings.cache_clear()
        try:
            with pytest.raises(ValidationError, match="拒绝启动"):
                get_settings()
        finally:
            get_settings.cache_clear()

    def test_env_driven_production_with_external_stores_accepted(self, monkeypatch):
        monkeypatch.setenv("XAGENT_APP_MODE", "production")
        monkeypatch.setenv("XAGENT_JWT_SECRET", _VALID_JWT)
        monkeypatch.setenv("XAGENT_ENCRYPTION_KEY", _VALID_ENC)
        monkeypatch.setenv("XAGENT_AUDIT_HMAC_SECRET", "hmac-secret")
        monkeypatch.setenv("XAGENT_REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("XAGENT_DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/xagent")
        monkeypatch.setenv("XAGENT_MEMORY_BACKEND", "postgres")
        monkeypatch.setenv("XAGENT_TRACE_BACKEND", "postgres")
        monkeypatch.setenv("XAGENT_ADMIN_STORE_BACKEND", "postgres")
        get_settings.cache_clear()
        try:
            settings = get_settings()
            assert settings.app_mode == "production"
            assert settings.admin_store_backend == "postgres"
        finally:
            get_settings.cache_clear()

    def test_env_driven_development_default_ok(self, monkeypatch):
        monkeypatch.delenv("XAGENT_APP_MODE", raising=False)
        get_settings.cache_clear()
        try:
            settings = get_settings()
            assert settings.app_mode != "production"
        finally:
            get_settings.cache_clear()
