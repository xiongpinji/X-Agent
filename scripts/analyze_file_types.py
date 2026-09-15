"""递归遍历项目目录，统计所有文件类型并生成详尽报告。

用法:
    python scripts/analyze_file_types.py [根目录] [-o 输出文件] [--no-ignore]

默认行为:
    - 从当前工作目录或项目根开始递归遍历
    - 忽略常见构建产物/虚拟环境/版本控制目录（如 .git, node_modules, venv, __pycache__ 等）
    - 输出按文件类型分组的统计报告，包含数量、总大小、平均大小、占比
    - 同时输出扩展名明细与目录分布概览

输出:
    - 控制台打印摘要
    - 默认在项目根生成 FILE_TYPE_REPORT.md
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# 默认忽略的目录名（构建产物 / 版本控制 / 依赖 / 缓存）
IGNORED_DIRS: frozenset = frozenset({
    ".git", ".hg", ".svn", ".idea", ".vscode", ".mypy_cache",
    "__pycache__", "node_modules", "venv", ".venv", "env", ".env",
    ".tox", ".pytest_cache", "dist", "build", ".ruff_cache", ".coverage",
    "htmlcov", "target", "out", ".eggs", "*.egg-info",
})

# 无扩展名文件的"类型"分类
NO_EXT = "(no-extension)"
DOTFILE = "(dotfile)"


def categorize(path: Path) -> Tuple[str, str]:
    """返回 (类别, 扩展名)。

    对于纯点文件（如 .gitignore）归入 DOTFILE；
    有扩展名则返回 (扩展名小写, 扩展名)，否则 NO_EXT。
    """
    name = path.name
    if name.startswith(".") and "." not in name[1:]:
        return DOTFILE, DOTFILE
    suffix = path.suffix.lower()
    if suffix:
        return suffix, suffix
    return NO_EXT, NO_EXT


def walk(root: Path, respect_ignore: bool) -> List[Path]:
    """递归收集文件。respect_ignore=True 时跳过忽略目录。"""
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if respect_ignore:
            dirnames[:] = [
                d for d in dirnames
                if not any(
                    d == ig or d.endswith(".egg-info")
                    for ig in IGNORED_DIRS if not ig.endswith("*")
                ) and not (d.startswith(".") and d in IGNORED_DIRS)
            ]
            # 额外处理通配形式（如 *.egg-info）已在上方覆盖
        for fn in filenames:
            files.append(Path(dirpath) / fn)
    return files


def human_size(num: int) -> str:
    """将字节数格式化为可读字符串。"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} B"
        num /= 1024
    return f"{num:.1f} TB"


def analyze(files: List[Path]) -> Dict[str, dict]:
    """聚合每个类型的 数量/总字节/文件列表。"""
    groups: Dict[str, dict] = defaultdict(lambda: {"count": 0, "bytes": 0, "files": []})
    for p in files:
        cat, _ext = categorize(p)
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        g = groups[cat]
        g["count"] += 1
        g["bytes"] += size
        g["files"].append((str(p), size))
    return groups


def build_report(
    root: Path,
    files: List[Path],
    groups: Dict[str, dict],
    respect_ignore: bool,
) -> str:
    """生成 Markdown 报告文本。"""
    total_count = len(files)
    total_bytes = sum(g["bytes"] for g in groups.values())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: List[str] = []
    lines.append("# 项目文件类型统计报告")
    lines.append("")
    lines.append(f"- **扫描根目录**: `{root}`")
    lines.append(f"- **生成时间**: {now}")
    lines.append(f"- **文件总数**: {total_count}")
    lines.append(f"- **目录总数**: {sum(1 for _ in root.rglob('*') if _.is_dir())}")
    lines.append(f"- **总大小**: {human_size(total_bytes)}")
    lines.append(f"- **忽略默认目录**: {'是' if respect_ignore else '否'}")
    lines.append("")

    # 按数量降序排序
    ordered = sorted(groups.items(), key=lambda kv: kv[1]["count"], reverse=True)

    lines.append("## 一、按文件类型汇总")
    lines.append("")
    lines.append("| 类型 | 数量 | 占比 | 总大小 | 平均大小 |")
    lines.append("|------|-----:|-----:|-------:|---------:|")
    for cat, g in ordered:
        pct = g["count"] / total_count * 100 if total_count else 0
        lines.append(
            f"| `{cat}` | {g['count']} | {pct:.2f}% | "
            f"{human_size(g['bytes'])} | {human_size(g['bytes'] // max(g['count'],1))} |"
        )
    lines.append("")

    lines.append("## 二、文件类型明细")
    lines.append("")
    for cat, g in ordered:
        lines.append(f"### `{cat}`  —  {g['count']} 个文件, 共 {human_size(g['bytes'])}")
        lines.append("")
        lines.append("| # | 相对路径 | 大小 |")
        lines.append("|---:|---------|-----:|")
        for i, (rel, size) in enumerate(sorted(g["files"]), 1):
            try:
                rel = os.path.relpath(rel, root)
            except ValueError:
                pass
            lines.append(f"| {i} | `{rel}` | {human_size(size)} |")
        lines.append("")

    lines.append("## 三、目录分布概览（Top 目录文件数）")
    lines.append("")
    dir_count: Dict[str, int] = defaultdict(int)
    for p in files:
        d = os.path.relpath(p.parent, root)
        dir_count["." if d == "." else d] += 1
    lines.append("| 目录 | 文件数 |")
    lines.append("|------|-------:|")
    for d, c in sorted(dir_count.items(), key=lambda kv: kv[1], reverse=True)[:30]:
        lines.append(f"| `{d}` | {c} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="递归统计项目文件类型并生成详尽报告")
    parser.add_argument("root", nargs="?", default=".", help="要扫描的根目录（默认当前目录）")
    parser.add_argument("-o", "--output", default="FILE_TYPE_REPORT.md", help="输出 Markdown 文件路径")
    parser.add_argument("--no-ignore", action="store_true", help="不忽略常见构建/依赖目录")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"错误: 目录不存在 -> {root}", file=sys.stderr)
        return 1

    respect_ignore = not args.no_ignore
    print(f"正在递归扫描: {root} ...")
    files = walk(root, respect_ignore=respect_ignore)
    groups = analyze(files)
    report = build_report(root, files, groups, respect_ignore=respect_ignore)

    out = Path(args.output)
    if not out.is_absolute():
        out = root / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")

    # 控制台摘要
    print(f"\n完成: 共扫描 {len(files)} 个文件, 分布如下 (按数量 Top 15):")
    for cat, g in sorted(groups.items(), key=lambda kv: kv[1]["count"], reverse=True)[:15]:
        pct = g["count"] / len(files) * 100 if files else 0
        print(f"  {cat:<20} {g['count']:>6}  ({pct:>6.2f}%)  {human_size(g['bytes'])}")
    print(f"\n详尽报告已写入: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
