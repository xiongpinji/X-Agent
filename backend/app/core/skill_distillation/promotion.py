"""P2-12: 技能沉淀 promote 最后一公里.

职责（单一）：
- 把 SkillDraft 落盘为 custom-skills/<name>/（SKILL.md + main.py）；
- 把 evolution_engine 自改进产物以新版本写回同一目录；
- 提供可复用的「落盘 → SkillLoader 热加载 → ToolRegistry 增量注册」入口
  （见 :func:`mount_skill`，配合 skill_agent_adapter.register_skill_into_tool_registry）。

设计原则：
- 落盘前校验（目录名安全、代码可编译、必须定义 SkillImplementation），
  校验失败抛异常由调用方 best-effort 降级，绝不写半成品目录；
- 幂等：同名重复 promote 覆盖写（版本升级场景）。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from backend.app.core.skill_distillation.generator import SkillDraft

logger = logging.getLogger(__name__)

# 目录名白名单：小写字母/数字/连字符（与 SkillLoader 的模块名约定兼容）
_UNSAFE_NAME_CHARS = re.compile(r"[^a-z0-9\-]+")


def sanitize_skill_name(name: str) -> str:
    """技能名 → 安全目录名（小写字母/数字/连字符）。"""
    sanitized = _UNSAFE_NAME_CHARS.sub("-", (name or "").strip().lower()).strip("-")
    return sanitized or "unnamed-skill"


def get_base_dir(base_dir: str | Path | None = None) -> Path:
    """返回落盘根目录（默认项目 custom-skills/）。"""
    if base_dir is not None:
        return Path(base_dir)
    from backend.app.core.skills import get_custom_skills_dir

    return get_custom_skills_dir()


def write_skill_package(draft: SkillDraft, base_dir: str | Path | None = None) -> Path:
    """把技能草稿落盘为可加载的技能目录（SKILL.md + main.py）。

    Returns:
        技能目录路径（custom-skills/<safe-name>/）。

    Raises:
        ValueError: 生成的 main.py 不含 SkillImplementation（模板损坏）。
    """
    skill_name = sanitize_skill_name(draft.name)
    main_py = draft.to_runtime_main_py()
    if "class SkillImplementation" not in main_py:
        raise ValueError(f"generated main.py for '{draft.name}' lacks SkillImplementation")
    compile(main_py, f"<skill:{skill_name}>", "exec")  # 语法校验，失败即抛

    skill_dir = get_base_dir(base_dir) / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(draft.to_skill_md(), encoding="utf-8")
    (skill_dir / "main.py").write_text(main_py, encoding="utf-8")
    logger.info("Skill package written: %s", skill_dir)
    return skill_dir


def persist_improved_skill(
    name: str,
    code: str,
    version: int,
    base_dir: str | Path | None = None,
) -> Path | None:
    """把自改进产物写回磁盘为新版本（best-effort 语义由调用方保证）。

    只接受完整模块源码（必须定义 ``class SkillImplementation`` 且可编译），
    避免把 LLM 返回的片段写坏现有技能目录。

    Returns:
        写入的 main.py 路径；目录不存在或代码不合规时返回 None。
    """
    skill_name = sanitize_skill_name(name)
    skill_dir = get_base_dir(base_dir) / skill_name
    if not (skill_dir / "main.py").is_file():
        logger.warning("persist_improved_skill: no existing package at %s, skip", skill_dir)
        return None
    if "class SkillImplementation" not in code:
        logger.warning("persist_improved_skill: improved code lacks SkillImplementation, skip")
        return None
    try:
        compile(code, f"<skill:{skill_name}:v{version}>", "exec")
    except SyntaxError as e:
        logger.warning("persist_improved_skill: improved code has syntax error, skip: %s", e)
        return None

    main_path = skill_dir / "main.py"
    main_path.write_text(code, encoding="utf-8")
    _bump_skill_md_version(skill_dir, version)
    logger.info("Skill improved on disk: %s (v%s)", main_path, version)
    return main_path


def _bump_skill_md_version(skill_dir: Path, version: int) -> None:
    """在 SKILL.md 尾部追加/更新版本标记行。"""
    md_path = skill_dir / "SKILL.md"
    if not md_path.is_file():
        return
    try:
        content = md_path.read_text(encoding="utf-8")
        marker = "*改进版本:"
        lines = [ln for ln in content.splitlines() if not ln.startswith(marker)]
        lines.append(f"{marker} v{version}*")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to bump SKILL.md version for %s: %s", skill_dir, e)


__all__ = [
    "persist_improved_skill",
    "sanitize_skill_name",
    "write_skill_package",
]
