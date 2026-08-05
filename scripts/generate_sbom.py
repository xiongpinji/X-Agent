#!/usr/bin/env python3
"""P1-05: 从 requirements-lock.txt 生成 CycloneDX SBOM (sbom.json)。

用法:
    venv/Scripts/python.exe scripts/generate_sbom.py [requirements-lock.txt] [sbom.json]

设计: 纯标准库解析 lock 文件 (name==version 行), cyclonedx-python-lib 组装
Bom。可重复执行, 供 CI 依赖治理流水线复用 (.github/workflows/security.yml)。
"""

from __future__ import annotations

import sys
from pathlib import Path

from cyclonedx.model.bom import Bom
from cyclonedx.model.component import Component, ComponentType
from cyclonedx.output.json import JsonV1Dot5
from packageurl import PackageURL


def parse_lock(lock_path: Path) -> list[tuple[str, str]]:
    """解析 requirements-lock.txt 的 name==version 条目（跳过注释/选项/editable）。"""
    entries: list[tuple[str, str]] = []
    for raw in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-", "--")):
            continue
        line = line.split(" ", 1)[0]  # 去掉行内注释/标记
        if "==" in line:
            name, version = line.split("==", 1)
            entries.append((name.strip(), version.strip()))
    return entries


def build_bom(entries: list[tuple[str, str]]) -> Bom:
    bom = Bom()
    for name, version in entries:
        bom.components.add(
            Component(
                name=name,
                version=version,
                type=ComponentType.LIBRARY,
                purl=PackageURL("pypi", name=name.lower().replace("_", "-"), version=version),
            )
        )
    return bom


def main() -> int:
    lock_path = Path(sys.argv[1] if len(sys.argv) > 1 else "requirements-lock.txt")
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else "sbom.json")
    entries = parse_lock(lock_path)
    if not entries:
        print(f"ERROR: no entries parsed from {lock_path}", file=sys.stderr)
        return 1
    bom = build_bom(entries)
    out_path.write_text(JsonV1Dot5(bom).output_as_string(indent=2), encoding="utf-8")
    print(f"SBOM written: {out_path} ({len(entries)} components, CycloneDX 1.5)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
