"""Work Mode 应用连接器抽象层。

提供统一接口连接外部应用（文件系统、Webhook、Slack 等），
供 WorkOrchestrator 在长任务中读写外部数据。
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class AppConnector(ABC):
    """应用连接器抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """连接器名称。"""

    @abstractmethod
    async def read(self, query: str) -> str:
        """从应用读取数据。"""

    @abstractmethod
    async def write(self, content: str, target: str = "") -> bool:
        """向应用写入数据。"""

    async def notify(self, message: str) -> bool:
        """发送通知（默认走 write）。"""
        return await self.write(message, target="notification")

    async def health_check(self) -> bool:
        """健康检查。"""
        return True


class FileConnector(AppConnector):
    """文件系统连接器 — 读写本地文件。"""

    def __init__(self, base_dir: str = "data/work_mode") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "file"

    async def read(self, query: str) -> str:
        """读取文件内容。query 为相对路径。"""
        path = self._base / query
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("FileConnector read failed: %s", exc)
            return ""

    async def write(self, content: str, target: str = "") -> bool:
        """写入文件。target 为相对路径。"""
        if not target:
            return False
        path = self._base / target
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(content, encoding="utf-8")
            return True
        except Exception as exc:
            logger.warning("FileConnector write failed: %s", exc)
            return False

    async def list_files(self, pattern: str = "*") -> list[str]:
        """列出匹配的文件。"""
        return [str(p.relative_to(self._base)) for p in self._base.glob(pattern)]


class WebhookConnector(AppConnector):
    """Webhook 连接器 — 通过 HTTP 回调与外部系统交互。"""

    def __init__(self, url: str = "", headers: dict[str, str] | None = None) -> None:
        self._url = url
        self._headers = headers or {"Content-Type": "application/json"}

    @property
    def name(self) -> str:
        return "webhook"

    async def read(self, query: str) -> str:
        """Webhook 不支持主动读取。"""
        return ""

    async def write(self, content: str, target: str = "") -> bool:
        """向 Webhook URL 发送 POST 请求。"""
        if not self._url:
            logger.warning("WebhookConnector: no URL configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                payload = {"content": content, "target": target}
                resp = await client.post(self._url, json=payload, headers=self._headers)
                return resp.status_code < 400
        except Exception as exc:
            logger.warning("WebhookConnector write failed: %s", exc)
            return False

    async def notify(self, message: str) -> bool:
        """发送通知到 Webhook。"""
        return await self.write(json.dumps({"type": "notification", "message": message}))


class MemoryConnector(AppConnector):
    """内存连接器 — 用于测试和临时数据存储。"""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "memory"

    async def read(self, query: str) -> str:
        return self._store.get(query, "")

    async def write(self, content: str, target: str = "") -> bool:
        if target:
            self._store[target] = content
            return True
        return False
