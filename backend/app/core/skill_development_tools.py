"""技能开发工具 - 脚手架、测试、打包、发布"""

from __future__ import annotations

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)


class SkillScaffold:
    """技能脚手架生成器"""

    SKILL_TEMPLATE = """# {name_zh}

## 概述

{description_zh}

## 功能

- 功能1
- 功能2
- 功能3

## 使用方法

### 基本用法

```python
from skills.{skill_id} import {class_name}

skill = {class_name}()
result = skill.execute(input_data)
```

### 参数

- `param1`: 参数1说明
- `param2`: 参数2说明

### 返回值

返回一个包含以下字段的字典:
- `status`: 执行状态 (success/error)
- `data`: 执行结果
- `error`: 错误信息（如果有）

## 示例

```python
result = skill.execute({
    "param1": "value1",
    "param2": "value2"
})
print(result)
```

## 常见问题

### Q: 如何配置技能？
A: 在 `config.json` 中配置相关参数。

### Q: 如何调试技能？
A: 使用 `skill test` 命令进行本地测试。

## 许可证

MIT
"""

    SKILL_MD_TEMPLATE = """# {name}

**中文名称**: {name_zh}

**版本**: {version}

**作者**: {author}

**分类**: {category}

## 描述

{description_zh}

## 能力

{capabilities}

## 依赖

{dependencies}

## 权限

{permissions}

## 入口点

{entry_point}

## 图标

{icon_emoji}
"""

    PYTHON_TEMPLATE = """\"\"\"
{name_zh} - {description_zh}
\"\"\"

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class {class_name}:
    \"\"\"
    {name_zh}技能
    \"\"\"

    def __init__(self):
        self.name = "{name}"
        self.version = "{version}"
        self.author = "{author}"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"
        执行技能

        Args:
            input_data: 输入数据

        Returns:
            执行结果
        \"\"\"
        try:
            # 验证输入
            self._validate_input(input_data)

            # 执行业务逻辑
            result = self._process(input_data)

            return {{
                "status": "success",
                "data": result,
            }}
        except Exception as e:
            logger.error(f"执行失败: {{e}}")
            return {{
                "status": "error",
                "error": str(e),
            }}

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        \"\"\"验证输入数据\"\"\"
        if not isinstance(input_data, dict):
            raise ValueError("输入必须是字典")

    def _process(self, input_data: Dict[str, Any]) -> Any:
        \"\"\"处理业务逻辑\"\"\"
        # 在这里实现你的业务逻辑
        return {{
            "message": "技能执行成功",
            "input": input_data,
        }}


# 导出技能类
__all__ = ["{class_name}"]
"""

    CONFIG_TEMPLATE = {{
        "name": "{{name}}",
        "name_zh": "{{name_zh}}",
        "version": "1.0.0",
        "author": "{{author}}",
        "description": "{{description}}",
        "description_zh": "{{description_zh}}",
        "category": "{{category}}",
        "icon_emoji": "{{icon_emoji}}",
        "keywords": [],
        "tags": [],
        "capabilities": [],
        "permissions": [],
        "dependencies": {{}},
    }}

    TEST_TEMPLATE = """\"\"\"
{name_zh}技能测试
\"\"\"

import pytest
from {skill_id} import {class_name}


@pytest.fixture
def skill():
    return {class_name}()


def test_execute_success(skill):
    \"\"\"测试成功执行\"\"\"
    result = skill.execute({{"param": "value"}})
    assert result["status"] == "success"
    assert "data" in result


def test_execute_error(skill):
    \"\"\"测试错误处理\"\"\"
    result = skill.execute(None)
    assert result["status"] == "error"
    assert "error" in result


def test_validate_input(skill):
    \"\"\"测试输入验证\"\"\"
    with pytest.raises(ValueError):
        skill._validate_input(None)
"""

    @staticmethod
    def create_skill(
        skill_name: str,
        name_zh: str,
        description: str,
        description_zh: str,
        author: str,
        category: str,
        icon_emoji: str = "🎯",
        output_dir: Optional[str] = None,
    ) -> str:
        """创建技能脚手架"""
        if output_dir is None:
            output_dir = os.getcwd()

        # 生成技能ID
        skill_id = skill_name.lower().replace(" ", "_").replace("-", "_")
        class_name = "".join(word.capitalize() for word in skill_id.split("_"))

        # 创建目录结构
        skill_dir = Path(output_dir) / skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)

        src_dir = skill_dir / "src"
        src_dir.mkdir(exist_ok=True)

        tests_dir = skill_dir / "tests"
        tests_dir.mkdir(exist_ok=True)

        # 创建 __init__.py
        (src_dir / "__init__.py").write_text(f"from .{skill_id} import {class_name}\n\n__all__ = ['{class_name}']\n")

        # 创建主技能文件
        skill_file = src_dir / f"{skill_id}.py"
        skill_file.write_text(SkillScaffold.PYTHON_TEMPLATE.format(
            name=skill_name,
            name_zh=name_zh,
            description=description,
            description_zh=description_zh,
            author=author,
            class_name=class_name,
            version="1.0.0",
        ))

        # 创建 SKILL.md
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(SkillScaffold.SKILL_MD_TEMPLATE.format(
            name=skill_name,
            name_zh=name_zh,
            version="1.0.0",
            author=author,
            category=category,
            description_zh=description_zh,
            capabilities="- 功能1\n- 功能2",
            dependencies="无",
            permissions="无",
            entry_point=f"src.{skill_id}.{class_name}",
            icon_emoji=icon_emoji,
        ))

        # 创建 README.md
        readme = skill_dir / "README.md"
        readme.write_text(SkillScaffold.SKILL_TEMPLATE.format(
            name_zh=name_zh,
            description_zh=description_zh,
            skill_id=skill_id,
            class_name=class_name,
        ))

        # 创建 config.json
        config = skill_dir / "config.json"
        config_data = SkillScaffold.CONFIG_TEMPLATE.copy()
        config_data.update({
            "name": skill_name,
            "name_zh": name_zh,
            "description": description,
            "description_zh": description_zh,
            "author": author,
            "category": category,
            "icon_emoji": icon_emoji,
        })
        config.write_text(json.dumps(config_data, indent=2, ensure_ascii=False))

        # 创建测试文件
        test_file = tests_dir / f"test_{skill_id}.py"
        test_file.write_text(SkillScaffold.TEST_TEMPLATE.format(
            name_zh=name_zh,
            skill_id=skill_id,
            class_name=class_name,
        ))

        # 创建 .gitignore
        gitignore = skill_dir / ".gitignore"
        gitignore.write_text("__pycache__/\n*.pyc\n.pytest_cache/\n.venv/\ndist/\nbuild/\n*.egg-info/\n")

        # 创建 requirements.txt
        requirements = skill_dir / "requirements.txt"
        requirements.write_text("# 在这里添加依赖\n")

        logger.info(f"技能脚手架已创建: {skill_dir}")
        return str(skill_dir)


class SkillTester:
    """技能本地测试工具"""

    @staticmethod
    async def test_skill(skill_dir: str) -> Dict[str, Any]:
        """运行技能测试"""
        skill_path = Path(skill_dir)

        if not skill_path.exists():
            return {"status": "error", "error": "技能目录不存在"}

        try:
            # 运行 pytest
            result = subprocess.run(
                ["python", "-m", "pytest", str(skill_path / "tests"), "-v"],
                cwd=str(skill_path),
                capture_output=True,
                text=True,
                timeout=60,
            )

            return {
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "测试超时"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class SkillPackager:
    """技能打包工具"""

    @staticmethod
    def package_skill(skill_dir: str, output_dir: Optional[str] = None) -> str:
        """打包技能"""
        skill_path = Path(skill_dir)

        if not skill_path.exists():
            raise ValueError("技能目录不存在")

        if output_dir is None:
            output_dir = os.getcwd()

        # 读取配置
        config_file = skill_path / "config.json"
        if not config_file.exists():
            raise ValueError("config.json 不存在")

        with open(config_file) as f:
            config = json.load(f)

        # 创建包名
        package_name = f"{config['name'].lower().replace(' ', '-')}-{config['version']}.tar.gz"
        output_path = Path(output_dir) / package_name

        # 打包
        shutil.make_archive(
            str(output_path.with_suffix("")),
            "gztar",
            skill_path.parent,
            skill_path.name,
        )

        logger.info(f"技能已打包: {output_path}")
        return str(output_path)


class SkillPublisher:
    """技能发布工具"""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    async def publish_skill(
        self,
        skill_dir: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """发布技能到市场"""
        skill_path = Path(skill_dir)

        if not skill_path.exists():
            return {"status": "error", "error": "技能目录不存在"}

        try:
            # 读取配置
            config_file = skill_path / "config.json"
            if not config_file.exists():
                return {"status": "error", "error": "config.json 不存在"}

            with open(config_file) as f:
                config = json.load(f)

            # 读取 README
            readme_file = skill_path / "README.md"
            readme_content = readme_file.read_text() if readme_file.exists() else ""

            # 准备发布数据
            publish_data = {
                "name": config.get("name"),
                "name_zh": config.get("name_zh"),
                "version": version or config.get("version", "1.0.0"),
                "category": config.get("category"),
                "description": config.get("description"),
                "description_zh": config.get("description_zh"),
                "author": config.get("author"),
                "icon_emoji": config.get("icon_emoji"),
                "keywords": config.get("keywords", []),
                "tags": config.get("tags", []),
            }

            # 调用 API 发布
            import aiohttp
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                async with session.post(
                    f"{self.api_url}/api/v1/skill-market/skills/publish",
                    json=publish_data,
                    headers=headers,
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        logger.info(f"技能已发布: {result}")
                        return {"status": "success", "data": result}
                    else:
                        error = await resp.text()
                        logger.error(f"发布失败: {error}")
                        return {"status": "error", "error": error}

        except Exception as e:
            logger.error(f"发布异常: {e}")
            return {"status": "error", "error": str(e)}


class SkillCLI:
    """技能开发命令行工具"""

    @staticmethod
    def create_command(args: Dict[str, Any]) -> None:
        """创建技能命令"""
        skill_dir = SkillScaffold.create_skill(
            skill_name=args["name"],
            name_zh=args["name_zh"],
            description=args.get("description", ""),
            description_zh=args.get("description_zh", ""),
            author=args.get("author", "Unknown"),
            category=args.get("category", "development"),
            icon_emoji=args.get("icon_emoji", "🎯"),
            output_dir=args.get("output_dir"),
        )
        print(f"技能已创建: {skill_dir}")

    @staticmethod
    async def test_command(args: Dict[str, Any]) -> None:
        """测试技能命令"""
        result = await SkillTester.test_skill(args["skill_dir"])
        print(json.dumps(result, indent=2, ensure_ascii=False))

    @staticmethod
    def package_command(args: Dict[str, Any]) -> None:
        """打包技能命令"""
        output_path = SkillPackager.package_skill(
            args["skill_dir"],
            args.get("output_dir"),
        )
        print(f"技能已打包: {output_path}")

    @staticmethod
    async def publish_command(args: Dict[str, Any]) -> None:
        """发布技能命令"""
        publisher = SkillPublisher(
            args["api_url"],
            args["api_key"],
        )
        result = await publisher.publish_skill(
            args["skill_dir"],
            args.get("version"),
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
