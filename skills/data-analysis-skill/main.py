"""数据分析助手 - 可执行实现

基于 Python 标准库 csv/statistics 的确定性 CSV 数据画像分析。
支持直接传入 CSV 文本或可读文件路径；不生成图表（无第三方绘图依赖），
输出结构化统计摘要，不做能力外承诺。
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List

from backend.app.core.skills import Skill, SkillContext, SkillMetadata, SkillResult

_MAX_ROWS = 100_000  # 防御性上限，避免超大输入拖垮进程


def _try_float(value: str) -> float | None:
    try:
        number = float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None
    return number if math.isfinite(number) else None


def _profile_column(name: str, values: List[str]) -> Dict[str, Any]:
    non_empty = [v for v in values if v is not None and str(v).strip() != ""]
    numeric = [n for n in (_try_float(v) for v in non_empty) if n is not None]

    profile: Dict[str, Any] = {
        "column": name,
        "rows": len(values),
        "non_empty": len(non_empty),
        "empty": len(values) - len(non_empty),
    }

    # 80% 以上可解析为数字 → 视为数值列
    if non_empty and len(numeric) / len(non_empty) >= 0.8 and numeric:
        profile["type"] = "numeric"
        profile["stats"] = {
            "count": len(numeric),
            "min": min(numeric),
            "max": max(numeric),
            "mean": statistics.fmean(numeric),
            "median": statistics.median(numeric),
            "stdev": statistics.stdev(numeric) if len(numeric) > 1 else 0.0,
            "sum": math.fsum(numeric),
        }
    else:
        profile["type"] = "text"
        frequencies: Dict[str, int] = {}
        for v in non_empty:
            frequencies[v] = frequencies.get(v, 0) + 1
        top = sorted(frequencies.items(), key=lambda kv: kv[1], reverse=True)[:5]
        profile["stats"] = {
            "distinct": len(frequencies),
            "top_values": [{"value": v, "count": c} for v, c in top],
        }
    return profile


class SkillImplementation(Skill):
    """数据分析技能：CSV 数据画像（列类型、数值统计、频次分布）"""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="data-analysis-skill",
            version="1.0.0",
            description="CSV 数据画像分析：列类型识别、数值统计、文本频次分布（纯标准库实现）",
            author="X-Agent Team",
            capabilities=["数据清洗", "统计分析", "报表生成"],
            tags=["data-analysis", "csv", "statistics"],
        )

    # LLM 工具调用参数 schema（供 skill_agent_adapter 使用）
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "csv_text": {
                "type": "string",
                "description": "CSV 文本内容（与 file_path 二选一）",
            },
            "file_path": {
                "type": "string",
                "description": "CSV 文件路径（与 csv_text 二选一）",
            },
            "has_header": {
                "type": "boolean",
                "description": "首行是否为表头",
                "default": True,
            },
        },
    }

    async def validate(self, context: SkillContext, **kwargs) -> bool:
        return bool(kwargs.get("csv_text") or kwargs.get("file_path"))

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        csv_text = kwargs.get("csv_text")
        file_path = kwargs.get("file_path")
        has_header = kwargs.get("has_header", True)

        if not csv_text and not file_path:
            return SkillResult(
                success=False,
                error="缺少输入：请提供 csv_text（CSV 文本）或 file_path（CSV 文件路径）之一",
            )

        if not csv_text:
            path = Path(str(file_path))
            if not path.is_file():
                return SkillResult(success=False, error=f"文件不存在或不可读: {file_path}")
            try:
                csv_text = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as e:
                return SkillResult(success=False, error=f"读取文件失败: {e}")

        try:
            reader = csv.reader(io.StringIO(csv_text))
            rows = [row for _, row in zip(range(_MAX_ROWS + 1), reader)]
        except csv.Error as e:
            return SkillResult(success=False, error=f"CSV 解析失败: {e}")

        if not rows:
            return SkillResult(success=False, error="CSV 内容为空")

        truncated = len(rows) > _MAX_ROWS
        rows = rows[:_MAX_ROWS]

        if has_header:
            header, data_rows = rows[0], rows[1:]
        else:
            width = max(len(r) for r in rows)
            header = [f"column_{i + 1}" for i in range(width)]
            data_rows = rows

        if not data_rows:
            return SkillResult(success=False, error="CSV 没有数据行（仅表头或空表）")

        width = len(header)
        columns: List[List[str]] = [[] for _ in range(width)]
        for row in data_rows:
            padded = list(row) + [""] * (width - len(row))
            for i in range(width):
                columns[i].append(padded[i])

        profiles = [_profile_column(name, values) for name, values in zip(header, columns)]

        return SkillResult(
            success=True,
            data={
                "source": "csv_text" if not file_path else str(file_path),
                "row_count": len(data_rows),
                "column_count": width,
                "truncated": truncated,
                "columns": profiles,
                "notes": "纯统计画像输出；本技能不生成图表（无绘图依赖），图表需由可视化工具另行生成。",
            },
        )


if __name__ == "__main__":
    # 手动冒烟：python skills/data-analysis-skill/main.py
    import asyncio
    import json

    sample = "city,sales\n北京,120\n上海,200\n北京,150\n广州,80\n"

    async def _smoke() -> None:
        skill = SkillImplementation()
        ctx = SkillContext(skill_name="data-analysis-skill", execution_id="smoke")
        result = await skill.execute(ctx, csv_text=sample)
        print(json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False, indent=2))

    asyncio.run(_smoke())
