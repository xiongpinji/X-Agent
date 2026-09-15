"""通知渠道配置存储 (backend/app/core/notification_config_store.py) 单测。

覆盖: CRUD / 落盘与重载 / 原子写(含失败清理) / 枚举校验 / 不可变字段 /
损坏文件逐条容错 / 单例与环境变量覆盖。
"""
import json
import time

import pytest
from pydantic import ValidationError

from backend.app.core.notification_config_store import (
    NOTIFICATION_TRIGGERS,
    NotificationConfigRecord,
    NotificationConfigStore,
    get_notification_config_store,
    reset_notification_config_store,
)


def _make_record(**overrides) -> NotificationConfigRecord:
    payload: dict = {
        "type": "email",
        "target": "ops@example.com",
        "triggers": ["new_feedback"],
    }
    payload.update(overrides)
    return NotificationConfigRecord(**payload)


@pytest.fixture(autouse=True)
def _isolate_singleton():
    """不让单例跨测试泄漏(它可能绑定到已销毁的 tmp_path)。"""
    reset_notification_config_store()
    yield
    reset_notification_config_store()


# ═══════════════════════════════════════════════════════════════════════════════
# 枚举契约
# ═══════════════════════════════════════════════════════════════════════════════

class TestTriggerEnum:
    def test_matches_frontend_contract(self):
        """锁定与 NotificationSettings.tsx 硬编码的 6 项完全一致。

        这是跨语言常量, 无法共享代码, 只能靠这条断言在漂移时炸出来。
        """
        assert set(NOTIFICATION_TRIGGERS) == {
            "new_feedback",
            "feedback_resolved",
            "high_priority_feedback",
            "critical_feedback",
            "sentiment_negative",
            "daily_summary",
        }
        assert len(NOTIFICATION_TRIGGERS) == 6

    def test_unknown_trigger_rejected(self):
        with pytest.raises(ValidationError):
            _make_record(triggers=["new_feedback", "carrier_pigeon"])

    def test_empty_triggers_allowed(self):
        """后端不做过严约束: 空列表不是脏数据(前端自己要求 >=1)。"""
        assert _make_record(triggers=[]).triggers == []


# ═══════════════════════════════════════════════════════════════════════════════
# 记录模型
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecordModel:
    def test_defaults(self):
        record = _make_record()
        assert record.enabled is True
        assert record.tenant_id == "default"
        assert record.id  # uuid4 自动生成
        assert record.created_at.tzinfo is not None
        assert record.updated_at.tzinfo is not None
        # 两个字段各有自己的 default_factory, 不承诺严格相等(实测差几微秒)。
        # 这里断言的是「同一时刻」, 足以抓到 updated_at 被写成陈旧值这类真 bug。
        assert abs((record.updated_at - record.created_at).total_seconds()) < 1

    def test_unique_ids(self):
        assert _make_record().id != _make_record().id

    def test_blank_target_rejected(self):
        """前端 `!formData.target` 即拒绝提交, 后端同口径。"""
        with pytest.raises(ValidationError):
            _make_record(target="")

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError):
            _make_record(type="sms")


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrud:
    def test_add_then_get(self, tmp_path):
        store = NotificationConfigStore(tmp_path / "cfg.json")
        record = _make_record()
        assert store.add(record) is record
        assert store.get(record.id) is record
        assert store.count() == 1

    def test_get_unknown_returns_none(self, tmp_path):
        store = NotificationConfigStore(tmp_path / "cfg.json")
        assert store.get("no-such-id") is None

    def test_add_does_not_dedupe(self, tmp_path):
        """显式创建刻意不去重 —— 静默合并会吞掉用户意图。"""
        store = NotificationConfigStore(tmp_path / "cfg.json")
        store.add(_make_record(target="ops@example.com"))
        store.add(_make_record(target="ops@example.com"))
        assert store.count() == 2

    def test_remove(self, tmp_path):
        store = NotificationConfigStore(tmp_path / "cfg.json")
        record = _make_record()
        store.add(record)
        assert store.remove(record.id) is True
        assert store.remove(record.id) is False  # 第二次已是 no-op
        assert store.count() == 0

    def test_list_for_tenant_isolates(self, tmp_path):
        store = NotificationConfigStore(tmp_path / "cfg.json")
        store.add(_make_record(tenant_id="acme"))
        store.add(_make_record(tenant_id="acme"))
        store.add(_make_record(tenant_id="globex"))
        assert len(store.list_for_tenant("acme")) == 2
        assert len(store.list_for_tenant("globex")) == 1
        assert store.list_for_tenant("nobody") == []
        assert store.count() == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 落盘 / 重载 / 原子写
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersistence:
    def test_survives_reload(self, tmp_path):
        path = tmp_path / "cfg.json"
        record = _make_record(target="reload@example.com")
        NotificationConfigStore(path).add(record)

        reloaded = NotificationConfigStore(path)
        assert reloaded.count() == 1
        got = reloaded.get(record.id)
        assert got is not None
        assert got.target == "reload@example.com"
        assert got.created_at == record.created_at
        assert got.triggers == ["new_feedback"]

    def test_remove_survives_reload(self, tmp_path):
        path = tmp_path / "cfg.json"
        store = NotificationConfigStore(path)
        record = _make_record()
        store.add(record)
        store.remove(record.id)
        assert NotificationConfigStore(path).count() == 0

    def test_payload_shape(self, tmp_path):
        path = tmp_path / "cfg.json"
        NotificationConfigStore(path).add(_make_record())
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert list(payload.keys()) == ["configs"]
        assert len(payload["configs"]) == 1
        assert payload["configs"][0]["type"] == "email"

    def test_missing_parent_dir_is_created(self, tmp_path):
        path = tmp_path / "nested" / "deeper" / "cfg.json"
        NotificationConfigStore(path).add(_make_record())
        assert path.exists()

    def test_no_temp_file_left_behind(self, tmp_path):
        store = NotificationConfigStore(tmp_path / "cfg.json")
        store.add(_make_record())
        store.add(_make_record())
        assert list(tmp_path.glob("*.tmp")) == []

    def test_atomic_write_cleans_temp_on_failure(self, tmp_path, monkeypatch):
        """os.replace 失败时: 异常照常抛出, 但临时文件必须被清掉。"""
        store = NotificationConfigStore(tmp_path / "cfg.json")

        def _boom(*_args, **_kwargs):
            raise OSError("simulated replace failure")

        monkeypatch.setattr(store.__class__.__module__ + ".os.replace", _boom)
        with pytest.raises(OSError, match="simulated replace failure"):
            store.add(_make_record())
        assert list(tmp_path.glob("*.tmp")) == []
        # 目标文件未被半写状态污染
        assert not (tmp_path / "cfg.json").exists()

    def test_missing_file_starts_empty(self, tmp_path):
        assert NotificationConfigStore(tmp_path / "absent.json").count() == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 损坏文件容错
# ═══════════════════════════════════════════════════════════════════════════════

class TestCorruptionTolerance:
    def test_garbage_json_starts_empty(self, tmp_path):
        path = tmp_path / "cfg.json"
        path.write_text("{ this is not json", encoding="utf-8")
        assert NotificationConfigStore(path).count() == 0

    def test_one_bad_record_does_not_drop_the_others(self, tmp_path):
        """逐条容错: 一处手误不该清空全部渠道。"""
        path = tmp_path / "cfg.json"
        good = _make_record(target="keep@example.com").model_dump(mode="json")
        path.write_text(
            json.dumps(
                {
                    "configs": [
                        good,
                        {"type": "carrier-pigeon", "target": "x"},  # 非法 type
                        {"type": "email", "target": ""},            # 空 target
                    ]
                }
            ),
            encoding="utf-8",
        )
        store = NotificationConfigStore(path)
        assert store.count() == 1
        assert store.list_for_tenant("default")[0].target == "keep@example.com"


# ═══════════════════════════════════════════════════════════════════════════════
# update()
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdate:
    def test_applies_changes_and_bumps_updated_at(self, tmp_path):
        path = tmp_path / "cfg.json"
        store = NotificationConfigStore(path)
        record = _make_record()
        store.add(record)

        time.sleep(0.01)  # 让时钟确实走一格, 否则断言可能因同刻取值而假通过
        updated = store.update(
            record.id,
            {"target": "new@example.com", "enabled": False, "triggers": ["daily_summary"]},
        )

        assert updated is not None
        assert updated.target == "new@example.com"
        assert updated.enabled is False
        assert updated.triggers == ["daily_summary"]
        assert updated.updated_at > record.updated_at
        assert updated.created_at == record.created_at  # 创建时间不动
        assert updated.id == record.id

    def test_persists_and_reloads(self, tmp_path):
        path = tmp_path / "cfg.json"
        store = NotificationConfigStore(path)
        record = _make_record()
        store.add(record)
        store.update(record.id, {"target": "persisted@example.com"})

        reloaded = NotificationConfigStore(path).get(record.id)
        assert reloaded is not None
        assert reloaded.target == "persisted@example.com"

    def test_unknown_id_returns_none(self, tmp_path):
        store = NotificationConfigStore(tmp_path / "cfg.json")
        assert store.update("no-such-id", {"enabled": False}) is None

    def test_unknown_field_raises(self, tmp_path):
        store = NotificationConfigStore(tmp_path / "cfg.json")
        record = _make_record()
        store.add(record)
        with pytest.raises(ValueError, match="not updatable"):
            store.update(record.id, {"troggers": ["new_feedback"]})  # 笔误
        assert store.get(record.id).triggers == ["new_feedback"]  # 未被污染

    @pytest.mark.parametrize("field", ["id", "tenant_id", "created_at"])
    def test_immutable_fields_raise(self, tmp_path, field):
        store = NotificationConfigStore(tmp_path / "cfg.json")
        record = _make_record()
        store.add(record)
        with pytest.raises(ValueError, match="not updatable"):
            store.update(record.id, {field: "anything"})

    def test_invalid_value_rejected_without_mutating(self, tmp_path):
        """合并不走校验就是隐患: 非法 triggers 必须在落盘前炸掉。"""
        store = NotificationConfigStore(tmp_path / "cfg.json")
        record = _make_record()
        store.add(record)
        with pytest.raises(ValidationError):
            store.update(record.id, {"triggers": ["carrier_pigeon"]})
        assert store.get(record.id).triggers == ["new_feedback"]


# ═══════════════════════════════════════════════════════════════════════════════
# 单例工厂
# ═══════════════════════════════════════════════════════════════════════════════

class TestSingleton:
    def test_returns_same_instance(self):
        assert get_notification_config_store() is get_notification_config_store()

    def test_reset_clears_instance(self):
        first = get_notification_config_store()
        reset_notification_config_store()
        assert get_notification_config_store() is not first

    def test_honours_env_var_path(self, tmp_path, monkeypatch):
        """环境变量覆盖路径 —— 用「文件真的在那个位置生成」来验证, 不看私有属性。"""
        target = tmp_path / "from_env.json"
        monkeypatch.setenv("XAGENT_NOTIFICATION_CONFIG_STORE_PATH", str(target))
        store = get_notification_config_store()
        store.add(_make_record())
        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8"))["configs"][0]["type"] == "email"

    def test_explicit_path_beats_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XAGENT_NOTIFICATION_CONFIG_STORE_PATH", str(tmp_path / "env.json"))
        explicit = tmp_path / "explicit.json"
        NotificationConfigStore(explicit).add(_make_record())
        assert explicit.exists()
        assert not (tmp_path / "env.json").exists()
