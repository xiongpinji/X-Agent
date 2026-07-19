# 技能市场完整开发指南

## 目录

1. [概述](#概述)
2. [架构设计](#架构设计)
3. [技能开发](#技能开发)
4. [技能发布](#技能发布)
5. [技能安装](#技能安装)
6. [最佳实践](#最佳实践)
7. [API参考](#api参考)
8. [常见问题](#常见问题)

## 概述

X-Agent 技能市场是一个完整的技能生态系统，允许开发者创建、发布和共享AI技能。技能市场支持：

- **200+个技能**：支持大规模技能库
- **快速安装**：<3秒安装时间
- **高效搜索**：<1秒搜索响应
- **完整分类**：8个主要分类
- **版本管理**：灵活的版本控制
- **依赖管理**：自动依赖解析
- **评分系统**：社区评价机制
- **使用统计**：详细的使用数据

## 架构设计

### 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    技能市场前端                          │
│  (React + TypeScript + Tailwind CSS)                    │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                    技能市场API                           │
│  (FastAPI + Python)                                     │
│  - 发布/审核/下架                                        │
│  - 搜索/分类/推荐                                        │
│  - 安装/卸载/更新                                        │
│  - 评分/评论/版本                                        │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  技能市场数据库                          │
│  (PostgreSQL)                                           │
│  - 技能表                                               │
│  - 版本表                                               │
│  - 评论表                                               │
│  - 安装表                                               │
│  - 使用记录表                                           │
└─────────────────────────────────────────────────────────┘
```

### 数据模型

#### 技能表 (skills)

```sql
CREATE TABLE skills (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    version TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    rating DECIMAL(3,2),
    rating_count INTEGER,
    downloads INTEGER,
    installed_count INTEGER,
    usage_count INTEGER,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ
);
```

#### 技能版本表 (skill_versions)

```sql
CREATE TABLE skill_versions (
    id UUID PRIMARY KEY,
    skill_id UUID NOT NULL REFERENCES skills(id),
    version TEXT NOT NULL,
    release_date TIMESTAMPTZ,
    changelog TEXT,
    download_count INTEGER
);
```

#### 技能评论表 (skill_reviews)

```sql
CREATE TABLE skill_reviews (
    id UUID PRIMARY KEY,
    skill_id UUID NOT NULL REFERENCES skills(id),
    user_id TEXT NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    title TEXT NOT NULL,
    comment TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ
);
```

#### 技能安装表 (skill_installations)

```sql
CREATE TABLE skill_installations (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    skill_id UUID NOT NULL REFERENCES skills(id),
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    config JSONB,
    created_at TIMESTAMPTZ
);
```

## 技能开发

### 创建技能脚手架

使用 `SkillScaffold` 快速创建技能项目：

```python
from backend.app.core.skill_development_tools import SkillScaffold

# 创建技能
skill_dir = SkillScaffold.create_skill(
    skill_name="My Awesome Skill",
    name_zh="我的超棒技能",
    description="A skill that does amazing things",
    description_zh="一个做很棒事情的技能",
    author="Your Name",
    category="development",
    icon_emoji="🚀",
    output_dir="/path/to/skills"
)
```

### 技能项目结构

```
my_skill/
├── src/
│   ├── __init__.py
│   └── my_skill.py          # 主技能文件
├── tests/
│   └── test_my_skill.py     # 测试文件
├── SKILL.md                 # 技能元数据
├── README.md                # 文档
├── config.json              # 配置文件
├── requirements.txt         # 依赖
└── .gitignore
```

### 实现技能类

```python
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class MySkill:
    """我的技能"""

    def __init__(self):
        self.name = "My Skill"
        self.version = "1.0.0"
        self.author = "Your Name"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行技能

        Args:
            input_data: 输入数据

        Returns:
            执行结果
        """
        try:
            # 验证输入
            self._validate_input(input_data)

            # 执行业务逻辑
            result = self._process(input_data)

            return {
                "status": "success",
                "data": result,
            }
        except Exception as e:
            logger.error(f"执行失败: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """验证输入数据"""
        if not isinstance(input_data, dict):
            raise ValueError("输入必须是字典")

    def _process(self, input_data: Dict[str, Any]) -> Any:
        """处理业务逻辑"""
        # 在这里实现你的业务逻辑
        return {
            "message": "技能执行成功",
            "input": input_data,
        }
```

### SKILL.md 格式

```markdown
# 我的技能

**中文名称**: 我的超棒技能

**版本**: 1.0.0

**作者**: Your Name

**分类**: development

## 描述

这是一个做很棒事情的技能。

## 能力

- 能力1
- 能力2
- 能力3

## 依赖

- 依赖1 >= 1.0.0
- 依赖2 >= 2.0.0

## 权限

- 读取文件
- 写入文件

## 入口点

src.my_skill.MySkill
```

## 技能发布

### 步骤1: 本地测试

```python
from backend.app.core.skill_development_tools import SkillTester

# 运行测试
result = await SkillTester.test_skill("/path/to/skill")
print(result)
```

### 步骤2: 打包技能

```python
from backend.app.core.skill_development_tools import SkillPackager

# 打包技能
package_path = SkillPackager.package_skill(
    "/path/to/skill",
    output_dir="/path/to/output"
)
print(f"技能已打包: {package_path}")
```

### 步骤3: 发布到市场

```python
from backend.app.core.skill_development_tools import SkillPublisher

# 创建发布器
publisher = SkillPublisher(
    api_url="https://api.x-agent.com",
    api_key="your_api_key"
)

# 发布技能
result = await publisher.publish_skill(
    "/path/to/skill",
    version="1.0.0"
)
print(result)
```

### API: 发布技能

```bash
POST /api/v1/skill-market/skills/publish

{
  "name": "My Skill",
  "name_zh": "我的技能",
  "version": "1.0.0",
  "category": "development",
  "description": "A skill that does amazing things",
  "description_zh": "一个做很棒事情的技能",
  "author": "Your Name",
  "icon_emoji": "🚀",
  "keywords": ["automation", "productivity"],
  "tags": ["useful", "fast"]
}
```

## 技能安装

### 用户安装技能

```bash
POST /api/v1/skill-market/skills/{skill_id}/install

{
  "version": "1.0.0",
  "config": {
    "option1": "value1"
  }
}
```

### 获取已安装技能

```bash
GET /api/v1/skill-market/my-skills
```

### 卸载技能

```bash
POST /api/v1/skill-market/skills/{skill_id}/uninstall
```

## 最佳实践

### 1. 代码质量

- 使用类型提示
- 添加详细的文档字符串
- 编写单元测试
- 遵循 PEP 8 风格指南

```python
def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行技能

    Args:
        input_data: 包含以下字段的字典:
            - param1 (str): 参数1说明
            - param2 (int): 参数2说明

    Returns:
        包含以下字段的字典:
            - status (str): 执行状态 (success/error)
            - data (Any): 执行结果
            - error (str): 错误信息（如果有）

    Raises:
        ValueError: 如果输入无效
    """
```

### 2. 错误处理

```python
def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # 验证输入
        if not input_data:
            raise ValueError("输入不能为空")

        # 执行业务逻辑
        result = self._process(input_data)

        return {
            "status": "success",
            "data": result,
        }
    except ValueError as e:
        logger.warning(f"输入验证失败: {e}")
        return {
            "status": "error",
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": "内部错误",
        }
```

### 3. 性能优化

- 缓存计算结果
- 使用异步操作
- 避免阻塞调用
- 优化数据库查询

```python
from functools import lru_cache

class MySkill:
    @lru_cache(maxsize=128)
    def _expensive_computation(self, key: str) -> Any:
        # 缓存计算结果
        return compute_something(key)
```

### 4. 安全性

- 验证所有输入
- 避免硬编码敏感信息
- 使用环境变量
- 实施访问控制

```python
import os
from typing import Optional

class MySkill:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        if not self.api_key:
            raise ValueError("API_KEY 环境变量未设置")

    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        if not isinstance(input_data, dict):
            raise ValueError("输入必须是字典")
        if "required_field" not in input_data:
            raise ValueError("缺少必需字段: required_field")
```

### 5. 文档

- 编写清晰的 README
- 提供使用示例
- 记录所有参数
- 解释返回值

```markdown
## 使用示例

### 基本用法

```python
from my_skill import MySkill

skill = MySkill()
result = skill.execute({
    "param1": "value1",
    "param2": "value2"
})
print(result)
```

### 参数说明

- `param1` (str): 参数1的说明
- `param2` (str): 参数2的说明

### 返回值

返回一个包含以下字段的字典:
- `status` (str): 执行状态
- `data` (dict): 执行结果
- `error` (str): 错误信息
```

## API参考

### 搜索技能

```bash
GET /api/v1/skill-market/skills/search?query=code&category=development&limit=20&offset=0
```

### 获取技能详情

```bash
GET /api/v1/skill-market/skills/{skill_id}
```

### 添加评论

```bash
POST /api/v1/skill-market/skills/{skill_id}/reviews

{
  "rating": 5,
  "title": "很棒的技能",
  "comment": "这个技能非常有用"
}
```

### 获取评论

```bash
GET /api/v1/skill-market/skills/{skill_id}/reviews?limit=20&offset=0
```

### 获取版本列表

```bash
GET /api/v1/skill-market/skills/{skill_id}/versions
```

### 创建新版本

```bash
POST /api/v1/skill-market/skills/{skill_id}/versions

{
  "version": "1.1.0",
  "changelog": "修复了一些bug，改进了性能"
}
```

### 获取市场统计

```bash
GET /api/v1/skill-market/stats
```

### 获取推荐

```bash
GET /api/v1/skill-market/recommendations?limit=10
```

## 常见问题

### Q: 如何快速创建一个技能？

A: 使用 `SkillScaffold.create_skill()` 方法快速生成项目结构。

### Q: 技能支持哪些编程语言？

A: 目前主要支持 Python。未来计划支持 JavaScript、Go 等。

### Q: 如何测试我的技能？

A: 使用 `SkillTester.test_skill()` 运行单元测试。

### Q: 技能可以依赖其他技能吗？

A: 可以。在 `SKILL.md` 中定义依赖，系统会自动解析。

### Q: 如何更新已发布的技能？

A: 创建新版本并发布。旧版本仍然可用。

### Q: 技能市场支持多少个技能？

A: 支持 200+ 个技能，可根据需要扩展。

### Q: 技能安装需要多长时间？

A: 通常 <3 秒。

### Q: 如何获取技能使用统计？

A: 调用 `/api/v1/skill-market/skills/{skill_id}/usage-stats` 端点。

### Q: 技能可以访问用户数据吗？

A: 可以，但需要用户授权。遵循最小权限原则。

### Q: 如何报告技能中的安全问题？

A: 联系安全团队：security@x-agent.com
