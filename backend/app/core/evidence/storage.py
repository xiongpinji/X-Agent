"""证据持久化存储（本地 JSON 文件）。"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.app.core.evidence.contracts import CompletionEvidence

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = Path("data/evidence")


class EvidenceStorage:
    """基于本地文件系统的证据存储。"""

    def __init__(self, store_dir: Path | str | None = None) -> None:
        self._dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, run_id: str) -> Path:
        safe_id = run_id.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe_id}.json"

    def save(self, evidence: CompletionEvidence) -> Path:
        """持久化证据包，返回文件路径。"""
        path = self._path_for(evidence.run_id)
        path.write_text(json.dumps(evidence.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"证据已保存: {path}")
        return path

    def load(self, run_id: str) -> CompletionEvidence | None:
        """加载证据包。"""
        path = self._path_for(run_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return CompletionEvidence.from_dict(data)

    def exists(self, run_id: str) -> bool:
        return self._path_for(run_id).exists()

    def delete(self, run_id: str) -> bool:
        path = self._path_for(run_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_all(self) -> list[str]:
        """列出所有已存储的 run_id。"""
        return [p.stem for p in self._dir.glob("*.json")]
