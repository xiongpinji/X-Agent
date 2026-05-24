from __future__ import annotations

import re
from pathlib import Path

# 精确匹配旧入口（core 下单文件模块名），避免把 open_source_* 误判为违规；
# 用 join 拼接模块路径，避免本文件出现完整字面量而被正则命中。
_LEGACY_OPEN_SOURCE_MODULE = ".".join(("backend", "app", "core", "open_source"))
_LEGACY_OPEN_SOURCE_IMPORT = re.compile(re.escape(_LEGACY_OPEN_SOURCE_MODULE) + r"\b")


def test_no_legacy_open_source_imports_remain() -> None:
    root = Path(__file__).resolve().parents[1]
    allowed = {
        root / "backend" / "app" / "core" / "open_source.py",
        root / "backend" / "app" / "core" / "open_source" / "__init__.py",
        root / "backend" / "app" / "core" / "open_source_base.py",
    }
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if _LEGACY_OPEN_SOURCE_IMPORT.search(text):
            offenders.append(str(path.relative_to(root)))
    assert not offenders, f"Legacy open_source imports still present: {offenders}"
