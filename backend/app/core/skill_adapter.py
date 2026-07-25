"""技能适配器 - 解析SKILL.md文件、验证格式、生成元数据"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from backend.app.core.skill_market_models import (
    SkillCategory,
    SkillManifest,
    SkillRecord,
    SkillStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsedSkillMetadata:
    """解析的技能元数据"""
    name: str
    name_zh: str
    version: str
    description: str
    description_zh: str
    author: str
    keywords: list[str]
    capabilities: list[str]
    icon_emoji: str
    repository: str


class SkillMarkdownParser:
    """SKILL.md文件解析器"""

    @staticmethod
    def parse_skill_md(content: str) -> ParsedSkillMetadata:
        """解析SKILL.md文件"""
        lines = content.split('\n')
        metadata = {
            'name': '',
            'name_zh': '',
            'version': '1.0.0',
            'description': '',
            'description_zh': '',
            'author': '',
            'keywords': [],
            'capabilities': [],
            'icon_emoji': '🎯',
            'repository': '',
        }

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 解析标题
            if line.startswith('# '):
                title = line[2:].strip()
                # 尝试分离中英文名称
                if '/' in title:
                    parts = title.split('/')
                    metadata['name'] = parts[0].strip()
                    metadata['name_zh'] = parts[1].strip()
                else:
                    metadata['name'] = title
                    metadata['name_zh'] = title

            # 解析版本
            elif line.startswith('**版本'):
                match = re.search(r':\s*([0-9.]+)', line)
                if match:
                    metadata['version'] = match.group(1)

            # 解析作者
            elif line.startswith('**作者'):
                match = re.search(r':\s*(.+?)(?:\*\*|$)', line)
                if match:
                    metadata['author'] = match.group(1).strip()

            # 解析描述
            elif line.startswith('**描述'):
                match = re.search(r':\s*(.+?)(?:\*\*|$)', line)
                if match:
                    metadata['description_zh'] = match.group(1).strip()

            # 解析关键词
            elif line.startswith('**关键词') or line.startswith('**Keywords'):
                match = re.search(r':\s*(.+?)(?:\*\*|$)', line)
                if match:
                    keywords_str = match.group(1).strip()
                    metadata['keywords'] = [k.strip() for k in keywords_str.split(',')]

            # 解析能力
            elif line.startswith('**能力') or line.startswith('**Capabilities'):
                match = re.search(r':\s*(.+?)(?:\*\*|$)', line)
                if match:
                    caps_str = match.group(1).strip()
                    metadata['capabilities'] = [c.strip() for c in caps_str.split(',')]

            # 解析图标
            elif line.startswith('**图标') or line.startswith('**Icon'):
                # 提取emoji
                emojis = re.findall(r'[\U0001F300-\U0001F9FF]', line)
                if emojis:
                    metadata['icon_emoji'] = emojis[0]

            # 解析仓库
            elif line.startswith('**仓库') or line.startswith('**Repository'):
                match = re.search(r':\s*(https?://[^\s]+)', line)
                if match:
                    metadata['repository'] = match.group(1)

            i += 1

        return ParsedSkillMetadata(**metadata)


class SkillAdapter:
    """技能适配器 - 将外部技能转换为内部格式"""

    @staticmethod
    def adapt_from_github(
        repo_name: str,
        skill_md_content: str,
        repo_url: str,
        category: SkillCategory,
    ) -> SkillRecord:
        """从GitHub仓库适配技能"""
        parsed = SkillMarkdownParser.parse_skill_md(skill_md_content)

        manifest = SkillManifest(
            name=parsed.name or repo_name,
            name_zh=parsed.name_zh or repo_name,
            version=parsed.version,
            author=parsed.author,
            description=parsed.description,
            description_zh=parsed.description_zh,
            keywords=parsed.keywords,
            capabilities=parsed.capabilities,
            icon_emoji=parsed.icon_emoji,
            repository=repo_url,
        )

        skill_id = f"skill_{repo_name.lower().replace(' ', '_').replace('-', '_')}"

        return SkillRecord(
            id=skill_id,
            manifest=manifest,
            category=category,
            status=SkillStatus.PUBLISHED,
            source_repo=repo_name,
            source_url=repo_url,
            source_type="github",
        )

    @staticmethod
    def adapt_from_gitee(
        repo_name: str,
        skill_md_content: str,
        repo_url: str,
        category: SkillCategory,
    ) -> SkillRecord:
        """从Gitee仓库适配技能"""
        parsed = SkillMarkdownParser.parse_skill_md(skill_md_content)

        manifest = SkillManifest(
            name=parsed.name or repo_name,
            name_zh=parsed.name_zh or repo_name,
            version=parsed.version,
            author=parsed.author,
            description=parsed.description,
            description_zh=parsed.description_zh,
            keywords=parsed.keywords,
            capabilities=parsed.capabilities,
            icon_emoji=parsed.icon_emoji,
            repository=repo_url,
        )

        skill_id = f"skill_{repo_name.lower().replace(' ', '_').replace('-', '_')}"

        return SkillRecord(
            id=skill_id,
            manifest=manifest,
            category=category,
            status=SkillStatus.PUBLISHED,
            source_repo=repo_name,
            source_url=repo_url,
            source_type="gitee",
        )

    @staticmethod
    def validate_skill_format(skill: SkillRecord) -> tuple[bool, list[str]]:
        """验证技能格式"""
        errors = []

        # 检查必需字段
        if not skill.manifest.name:
            errors.append("技能名称不能为空")
        if not skill.manifest.name_zh:
            errors.append("技能中文名称不能为空")
        if not skill.manifest.version:
            errors.append("版本号不能为空")

        # 检查版本格式
        if skill.manifest.version and not re.match(r'^\d+\.\d+\.\d+', skill.manifest.version):
            errors.append(f"版本号格式不正确: {skill.manifest.version}")

        # 检查描述
        if not skill.manifest.description_zh:
            errors.append("中文描述不能为空")

        # 检查分类
        if not skill.category:
            errors.append("分类不能为空")

        return len(errors) == 0, errors

    @staticmethod
    def generate_metadata(skill: SkillRecord) -> dict[str, Any]:
        """生成技能元数据"""
        return {
            "id": skill.id,
            "name": skill.manifest.name,
            "name_zh": skill.manifest.name_zh,
            "version": skill.manifest.version,
            "category": skill.category.value,
            "status": skill.status.value,
            "author": skill.manifest.author,
            "description": skill.manifest.description_zh,
            "keywords": skill.manifest.keywords,
            "capabilities": skill.manifest.capabilities,
            "icon": skill.manifest.icon_emoji,
            "rating": skill.rating,
            "downloads": skill.downloads,
            "installed": skill.is_installed,
            "source": {
                "type": skill.source_type,
                "repo": skill.source_repo,
                "url": skill.source_url,
            },
            "created_at": skill.created_at.isoformat(),
            "updated_at": skill.updated_at.isoformat(),
        }


class SkillParameterValidator:
    """技能参数验证器"""

    @staticmethod
    def validate_parameters(
        skill_id: str,
        input_data: dict[str, Any],
        expected_params: dict[str, str] | None = None,
    ) -> tuple[bool, list[str]]:
        """验证技能参数"""
        errors = []

        if expected_params:
            for param_name, param_type in expected_params.items():
                if param_name not in input_data:
                    errors.append(f"缺少必需参数: {param_name}")
                else:
                    # 简单的类型检查
                    value = input_data[param_name]
                    if param_type == "string" and not isinstance(value, str):
                        errors.append(f"参数 {param_name} 应该是字符串")
                    elif param_type == "number" and not isinstance(value, (int, float)):
                        errors.append(f"参数 {param_name} 应该是数字")
                    elif param_type == "boolean" and not isinstance(value, bool):
                        errors.append(f"参数 {param_name} 应该是布尔值")
                    elif param_type == "array" and not isinstance(value, list):
                        errors.append(f"参数 {param_name} 应该是数组")

        return len(errors) == 0, errors
