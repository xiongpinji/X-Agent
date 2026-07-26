"""用户反馈 JSON 文件存储 - 无数据库 dev 环境的显式降级实现。

与 ``backend.app.models.feedback.FeedbackStorePostgres`` 的 public async 方法集
完全一致(create_feedback / get_feedback_by_id / list_feedback / update_feedback /
create_analysis / get_analysis_by_feedback_id / count_feedback / delete_feedback /
search_feedback), 返回同样的 ORM 模型实例(未挂 session 的瞬态对象, 属性访问
与 Postgres 路径一致)。

与 workflow_store 的 ``auto`` 模式同哲学: Postgres 不可用时由
``backend.app.api.feedback.get_feedback_store`` 显式降级到本实现(WARNING 一次),
不静默、不报错。

持久化: 单 JSON 文件, 原子写(同目录临时文件 + os.replace), threading.RLock
串行化读写。存储路径由 ``XAGENT_FEEDBACK_STORE_PATH`` 指定, 默认
``<repo_root>/data/feedback_store.json``。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from backend.app.models.feedback import FeedbackAnalysisModel, FeedbackModel

logger = logging.getLogger(__name__)

FEEDBACK_STORE_PATH_ENV = "XAGENT_FEEDBACK_STORE_PATH"

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "feedback_store.json"

_DT_FIELDS = ("created_at", "updated_at", "resolved_at")


def _default_path() -> Path:
    return Path(os.getenv(FEEDBACK_STORE_PATH_ENV) or _DEFAULT_PATH)


def _parse_dt(value: Any) -> datetime | None:
    """从 ISO 字符串/None 恢复 datetime; naive 一律按 UTC 处理(与 API 层一致)。"""
    if value is None or isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value))
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _serialize_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _feedback_to_dict(f: FeedbackModel) -> dict[str, Any]:
    return {
        "id": f.id,
        "user_id": f.user_id,
        "tenant_id": f.tenant_id,
        "feedback_type": f.feedback_type,
        "title": f.title,
        "description": f.description,
        "severity": f.severity,
        "status": f.status,
        "sentiment": f.sentiment,
        "sentiment_score": f.sentiment_score,
        "priority_score": f.priority_score,
        "category": f.category,
        "tags": f.tags,
        "extra_metadata": f.extra_metadata,
        "created_at": _serialize_dt(f.created_at),
        "updated_at": _serialize_dt(f.updated_at),
        "resolved_at": _serialize_dt(f.resolved_at),
    }


def _feedback_from_dict(d: dict[str, Any]) -> FeedbackModel:
    return FeedbackModel(
        id=d["id"],
        user_id=d["user_id"],
        tenant_id=d["tenant_id"],
        feedback_type=d["feedback_type"],
        title=d["title"],
        description=d["description"],
        severity=d["severity"],
        status=d.get("status", "new"),
        sentiment=d.get("sentiment"),
        sentiment_score=d.get("sentiment_score"),
        priority_score=d.get("priority_score"),
        category=d.get("category"),
        tags=d.get("tags"),
        extra_metadata=d.get("extra_metadata") or {},
        created_at=_parse_dt(d.get("created_at")),
        updated_at=_parse_dt(d.get("updated_at")),
        resolved_at=_parse_dt(d.get("resolved_at")),
    )


def _analysis_to_dict(a: FeedbackAnalysisModel) -> dict[str, Any]:
    return {
        "id": a.id,
        "feedback_id": a.feedback_id,
        "sentiment_score": a.sentiment_score,
        "sentiment_type": a.sentiment_type,
        "category": a.category,
        "subcategory": a.subcategory,
        "tags": a.tags,
        "priority_score": a.priority_score,
        "urgency_score": a.urgency_score,
        "impact_score": a.impact_score,
        "keywords": a.keywords,
        "entities": a.entities,
        "analysis_metadata": a.analysis_metadata,
        "created_at": _serialize_dt(a.created_at),
        "updated_at": _serialize_dt(a.updated_at),
    }


def _analysis_from_dict(d: dict[str, Any]) -> FeedbackAnalysisModel:
    return FeedbackAnalysisModel(
        id=d["id"],
        feedback_id=d["feedback_id"],
        sentiment_score=d["sentiment_score"],
        sentiment_type=d["sentiment_type"],
        category=d["category"],
        subcategory=d.get("subcategory"),
        tags=d.get("tags") or [],
        priority_score=d["priority_score"],
        urgency_score=d["urgency_score"],
        impact_score=d["impact_score"],
        keywords=d.get("keywords") or [],
        entities=d.get("entities") or {},
        analysis_metadata=d.get("analysis_metadata") or {},
        created_at=_parse_dt(d.get("created_at")),
        updated_at=_parse_dt(d.get("updated_at")),
    )


class FeedbackStoreFile:
    """JSON 文件反馈存储(dev 降级), 接口与 FeedbackStorePostgres 完全一致。"""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._path = Path(storage_path) if storage_path else _default_path()
        self._lock = RLock()

    # ------------------------------------------------------------------
    # 持久化(原子写)
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"feedback": {}, "analysis": {}}
        with self._path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("feedback", {})
        data.setdefault("analysis", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._path.parent),
            prefix=self._path.name + ".",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self._path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # 与 FeedbackStorePostgres 一致的 public async 方法集
    # ------------------------------------------------------------------

    async def create_feedback(
        self,
        feedback_id: str,
        user_id: str,
        tenant_id: str,
        feedback_type: str,
        title: str,
        description: str,
        severity: str,
        metadata: dict | None = None,
    ) -> FeedbackModel:
        """创建反馈"""
        now = datetime.now(UTC)
        with self._lock:
            data = self._load()
            feedback = FeedbackModel(
                id=feedback_id,
                user_id=user_id,
                tenant_id=tenant_id,
                feedback_type=feedback_type,
                title=title,
                description=description,
                severity=severity,
                status="new",
                extra_metadata=metadata or {},
                created_at=now,
                updated_at=now,
            )
            data["feedback"][feedback_id] = _feedback_to_dict(feedback)
            self._save(data)
        logger.info(f"反馈创建成功(文件存储): {feedback_id}")
        return feedback

    async def get_feedback_by_id(self, feedback_id: str) -> FeedbackModel | None:
        """根据ID获取反馈"""
        with self._lock:
            data = self._load()
        record = data["feedback"].get(feedback_id)
        return _feedback_from_dict(record) if record else None

    async def list_feedback(
        self,
        tenant_id: str,
        user_id: str | None = None,
        feedback_type: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FeedbackModel]:
        """列出反馈(created_at 倒序, 强制 tenant 收敛)"""
        with self._lock:
            data = self._load()
        items = [
            _feedback_from_dict(r)
            for r in data["feedback"].values()
            if r.get("tenant_id") == tenant_id
            and (user_id is None or r.get("user_id") == user_id)
            and (feedback_type is None or r.get("feedback_type") == feedback_type)
            and (status is None or r.get("status") == status)
            and (severity is None or r.get("severity") == severity)
        ]
        items.sort(key=lambda f: f.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return items[skip : skip + limit]

    async def update_feedback(
        self,
        feedback_id: str,
        **kwargs,
    ) -> FeedbackModel | None:
        """更新反馈"""
        with self._lock:
            data = self._load()
            record = data["feedback"].get(feedback_id)
            if not record:
                return None

            feedback = _feedback_from_dict(record)
            for key, value in kwargs.items():
                if hasattr(feedback, key):
                    setattr(feedback, key, value)

            feedback.updated_at = datetime.now(UTC)
            data["feedback"][feedback_id] = _feedback_to_dict(feedback)
            self._save(data)
        logger.info(f"反馈更新成功(文件存储): {feedback_id}")
        return feedback

    async def create_analysis(
        self,
        analysis_id: str,
        feedback_id: str,
        sentiment_score: float,
        sentiment_type: str,
        category: str,
        tags: list[str],
        priority_score: float,
        urgency_score: float,
        impact_score: float,
        subcategory: str | None = None,
        keywords: list[str] | None = None,
        entities: dict | None = None,
        analysis_metadata: dict | None = None,
    ) -> FeedbackAnalysisModel:
        """创建反馈分析"""
        now = datetime.now(UTC)
        with self._lock:
            data = self._load()
            analysis = FeedbackAnalysisModel(
                id=analysis_id,
                feedback_id=feedback_id,
                sentiment_score=sentiment_score,
                sentiment_type=sentiment_type,
                category=category,
                subcategory=subcategory,
                tags=tags,
                priority_score=priority_score,
                urgency_score=urgency_score,
                impact_score=impact_score,
                keywords=keywords or [],
                entities=entities or {},
                analysis_metadata=analysis_metadata or {},
                created_at=now,
                updated_at=now,
            )
            data["analysis"][analysis_id] = _analysis_to_dict(analysis)
            self._save(data)
        logger.info(f"反馈分析创建成功(文件存储): {analysis_id}")
        return analysis

    async def get_analysis_by_feedback_id(self, feedback_id: str) -> FeedbackAnalysisModel | None:
        """根据反馈ID获取分析"""
        with self._lock:
            data = self._load()
        for record in data["analysis"].values():
            if record.get("feedback_id") == feedback_id:
                return _analysis_from_dict(record)
        return None

    async def count_feedback(
        self,
        tenant_id: str,
        status: str | None = None,
        severity: str | None = None,
    ) -> int:
        """统计反馈数量"""
        with self._lock:
            data = self._load()
        return sum(
            1
            for r in data["feedback"].values()
            if r.get("tenant_id") == tenant_id
            and (status is None or r.get("status") == status)
            and (severity is None or r.get("severity") == severity)
        )

    async def delete_feedback(self, feedback_id: str) -> bool:
        """删除反馈及其分析记录, 返回是否删除成功"""
        with self._lock:
            data = self._load()
            if feedback_id not in data["feedback"]:
                return False
            del data["feedback"][feedback_id]
            # 级联删除关联的分析记录
            data["analysis"] = {
                aid: r
                for aid, r in data["analysis"].items()
                if r.get("feedback_id") != feedback_id
            }
            self._save(data)
        logger.info(f"反馈删除成功(文件存储): {feedback_id}")
        return True

    async def search_feedback(
        self,
        tenant_id: str,
        keyword: str,
        user_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FeedbackModel]:
        """按关键词搜索反馈(标题/描述), 强制租户收敛"""
        with self._lock:
            data = self._load()
        items = [
            _feedback_from_dict(r)
            for r in data["feedback"].values()
            if r.get("tenant_id") == tenant_id
            and (user_id is None or r.get("user_id") == user_id)
            and (keyword in (r.get("title") or "") or keyword in (r.get("description") or ""))
        ]
        items.sort(key=lambda f: f.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return items[skip : skip + limit]
