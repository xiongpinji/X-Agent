"""
X-Agent 技能系统文档 - 完整的技能开发指南、API文档、最佳实践
"""

# X-Agent 技能系统完整文档

## 目录

1. [概述](#概述)
2. [核心概念](#核心概念)
3. [技能开发指南](#技能开发指南)
4. [技能市场](#技能市场)
5. [技能链](#技能链)
6. [技能审核](#技能审核)
7. [API参考](#api参考)
8. [最佳实践](#最佳实践)
9. [常见问题](#常见问题)

---

## 概述

X-Agent 技能系统是一个完整的技能管理、执行和市场平台，支持：

- **技能定义和注册**: 标准化的技能元数据和参数定义
- **技能执行**: 安全的技能执行引擎，支持超时、重试、资源限制
- **技能链**: 支持顺序、并行、条件和循环执行的技能组合
- **技能市场**: 完整的技能发现、安装、评分和版本管理
- **技能审核**: 自动化的安全、性能、功能和文档检查

---

## 核心概念

### 技能 (Skill)

技能是一个可执行的功能单元，具有以下特征：

- **元数据**: 名称、版本、描述、作者等
- **参数**: 输入参数定义和验证规则
- **能力**: 技能提供的功能能力
- **依赖**: 技能依赖的其他技能或库
- **资源限制**: 超时、内存、CPU限制
- **安全性**: 风险等级、所需权限

### 技能执行上下文 (SkillExecutionContext)

执行上下文包含：

- 执行ID: 唯一标识一次执行
- 用户ID和租户ID: 执行的用户和租户
- 输入数据: 技能的输入参数
- 输出数据: 技能的执行结果
- 执行状态: PENDING, RUNNING, SUCCESS, FAILED, TIMEOUT, CANCELLED
- 资源使用: CPU和内存使用情况

### 技能链 (SkillChain)

技能链支持多种执行模式：

- **顺序执行 (Sequential)**: 按顺序执行步骤，前一步的输出作为后一步的输入
- **并行执行 (Parallel)**: 同时执行多个步骤
- **条件执行 (Conditional)**: 根据条件选择执行不同的步骤
- **循环执行 (Loop)**: 支持FOR、WHILE、FOREACH循环

---

## 技能开发指南

### 1. 创建技能类

```python
from backend.app.core.skill_system_v2 import (
    Skill, SkillMetadata, SkillExecutionContext, SkillExecutionResult,
    SkillParameter, SkillCategory, SkillRiskLevel, ExecutionStatus
)
from datetime import datetime, UTC

class MySkill(Skill):
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="my-skill",
            name_zh="我的技能",
            version="1.0.0",
            description="A sample skill",
            description_zh="一个示例技能",
            author="Your Name",
            category=SkillCategory.PRODUCTIVITY,
            icon_emoji="🚀",
            capabilities=["text:generate"],
            parameters=[
                SkillParameter(
                    name="input_text",
                    type="string",
                    description="Input text to process",
                    required=True,
                ),
                SkillParameter(
                    name="max_length",
                    type="number",
                    description="Maximum output length",
                    required=False,
                    default=100,
                    min_value=1,
                    max_value=1000,
                ),
            ],
            tags=["text", "processing"],
            keywords=["text", "generate"],
            documentation_url="https://example.com/docs",
            repository_url="https://github.com/example/my-skill",
        )

    async def execute(
        self, context: SkillExecutionContext, **kwargs
    ) -> SkillExecutionResult:
        try:
            input_text = kwargs.get("input_text", "")
            max_length = kwargs.get("max_length", 100)

            # Your skill logic here
            result = f"Processed: {input_text[:max_length]}"

            return SkillExecutionResult(
                success=True,
                data={"result": result},
                execution_time_ms=0.0,
            )
        except Exception as e:
            return SkillExecutionResult(
                success=False,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def initialize(self) -> None:
        # Initialize resources
        pass

    async def cleanup(self) -> None:
        # Cleanup resources
        pass
```

### 2. 注册技能

```python
from backend.app.core.skill_system_v2 import get_skill_registry

async def register_skill():
    registry = get_skill_registry()
    skill = MySkill()
    await registry.register(skill)
```

### 3. 执行技能

```python
from backend.app.core.skill_system_v2 import get_skill_executor

async def execute_skill():
    executor = get_skill_executor()
    result = await executor.execute(
        skill_name="my-skill",
        input_data={"input_text": "Hello World", "max_length": 50},
        user_id="user123",
        tenant_id="tenant123",
    )
    print(result.to_dict())
```

---

## 技能市场

### 发布技能

```python
from backend.app.api.skill_marketplace import SkillPublishRequest

request = SkillPublishRequest(
    name="my-skill",
    name_zh="我的技能",
    version="1.0.0",
    category="productivity",
    description="A sample skill",
    description_zh="一个示例技能",
    author="Your Name",
    icon_emoji="🚀",
    keywords=["text", "generate"],
    tags=["productivity"],
)

# POST /api/v1/skills/publish
```

### 搜索技能

```python
# GET /api/v1/skills/search?query=text&category=productivity&min_rating=4.0
```

### 安装技能

```python
from backend.app.api.skill_marketplace import SkillInstallRequest

request = SkillInstallRequest(
    skill_id="skill-id",
    version="1.0.0",
)

# POST /api/v1/skills/install
```

### 评分技能

```python
from backend.app.api.skill_marketplace import SkillRatingRequest

request = SkillRatingRequest(
    skill_id="skill-id",
    rating=5,
    title="Great skill!",
    comment="Very useful and well documented",
)

# POST /api/v1/skills/{skill_id}/rate
```

---

## 技能链

### 创建顺序链

```python
from backend.app.core.skill_chain import (
    SkillChain, ChainStep, ChainType
)

chain = SkillChain(
    name="text-processing-chain",
    description="Process text through multiple skills",
    chain_type=ChainType.SEQUENTIAL,
    steps=[
        ChainStep(
            name="extract-text",
            skill_name="text-extractor",
            input_mapping={"source": "input_file"},
            output_mapping={"extracted_text": "text"},
        ),
        ChainStep(
            name="analyze-text",
            skill_name="text-analyzer",
            input_mapping={"text": "extracted_text"},
            output_mapping={"analysis": "result"},
        ),
    ],
)
```

### 创建并行链

```python
chain = SkillChain(
    name="parallel-processing",
    chain_type=ChainType.PARALLEL,
    steps=[
        ChainStep(name="task1", skill_name="skill1"),
        ChainStep(name="task2", skill_name="skill2"),
        ChainStep(name="task3", skill_name="skill3"),
    ],
)
```

### 创建条件链

```python
from backend.app.core.skill_chain import ConditionalStep

chain = SkillChain(
    name="conditional-processing",
    chain_type=ChainType.CONDITIONAL,
    steps=[
        ConditionalStep(
            condition="input_data.get('type') == 'urgent'",
            then_steps=[
                ChainStep(name="urgent-process", skill_name="urgent-skill"),
            ],
            else_steps=[
                ChainStep(name="normal-process", skill_name="normal-skill"),
            ],
        ),
    ],
)
```

### 执行链

```python
from backend.app.core.skill_chain import get_skill_chain_executor

executor = get_skill_chain_executor()
context = await executor.execute_chain(
    chain=chain,
    input_data={"input_file": "data.txt"},
    user_id="user123",
    tenant_id="tenant123",
)
print(context.to_dict())
```

---

## 技能审核

### 审核流程

1. **自动检查**: 安全、性能、功能、文档、兼容性检查
2. **问题识别**: 识别CRITICAL、ERROR、WARNING、INFO级别的问题
3. **评分计算**: 基于各项检查结果计算总分
4. **状态确定**: 根据问题和分数确定审核状态
5. **人工审核**: 审核员进行最终审核和批准

### 审核状态

- **PENDING**: 等待审核
- **IN_REVIEW**: 审核中
- **APPROVED**: 已批准
- **REJECTED**: 已拒绝
- **NEEDS_REVISION**: 需要修改
- **APPROVED_WITH_CONDITIONS**: 有条件批准

### 审核检查项

#### 安全检查 (Security Check)
- 风险等级评估
- 依赖安全性
- 权限检查
- 网络访问检查
- 数据处理检查

#### 性能检查 (Performance Check)
- 超时时间检查
- 内存使用检查
- CPU使用检查

#### 功能检查 (Functionality Check)
- 必需字段检查
- 参数定义检查
- 能力定义检查

#### 文档检查 (Documentation Check)
- 描述完整性检查
- 文档URL检查
- 仓库URL检查

#### 兼容性检查 (Compatibility Check)
- 版本格式检查
- 许可证检查

---

## API参考

### 技能执行API

#### 执行技能
```
POST /api/v1/skills/execute
Content-Type: application/json

{
  "skill_name": "my-skill",
  "input_data": {
    "input_text": "Hello World"
  }
}

Response:
{
  "success": true,
  "data": {
    "result": "Processed: Hello World"
  },
  "execution_time_ms": 123.45
}
```

### 技能市场API

#### 搜索技能
```
GET /api/v1/skills/search?query=text&category=productivity&limit=20&offset=0
```

#### 获取技能详情
```
GET /api/v1/skills/{skill_id}
```

#### 发布技能
```
POST /api/v1/skills/publish
Content-Type: application/json

{
  "name": "my-skill",
  "version": "1.0.0",
  ...
}
```

#### 安装技能
```
POST /api/v1/skills/install
Content-Type: application/json

{
  "skill_id": "skill-id",
  "version": "1.0.0"
}
```

#### 评分技能
```
POST /api/v1/skills/{skill_id}/rate
Content-Type: application/json

{
  "rating": 5,
  "title": "Great skill!",
  "comment": "Very useful"
}
```

### 技能链API

#### 创建链
```
POST /api/v1/skills/chains/create
Content-Type: application/json

{
  "name": "my-chain",
  "chain_type": "sequential",
  "steps": [...]
}
```

#### 执行链
```
POST /api/v1/skills/chains/{chain_id}/execute
Content-Type: application/json

{
  "input_data": {...}
}
```

#### 获取执行结果
```
GET /api/v1/skills/chains/{chain_id}/executions/{execution_id}
```

---

## 最佳实践

### 1. 参数验证

始终验证输入参数：

```python
async def validate_input(self, input_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    # 使用基类的验证方法
    return await super().validate_input(input_data)
```

### 2. 错误处理

提供清晰的错误信息：

```python
try:
    # Your logic
except ValueError as e:
    return SkillExecutionResult(
        success=False,
        error=str(e),
        error_type="ValidationError",
    )
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    return SkillExecutionResult(
        success=False,
        error="Internal server error",
        error_type="InternalError",
    )
```

### 3. 资源管理

正确初始化和清理资源：

```python
async def initialize(self) -> None:
    # Initialize connections, load models, etc.
    self.connection = await create_connection()

async def cleanup(self) -> None:
    # Close connections, free memory, etc.
    if self.connection:
        await self.connection.close()
```

### 4. 文档

提供完整的文档：

```python
metadata = SkillMetadata(
    name="my-skill",
    description="Clear and concise description",
    documentation_url="https://example.com/docs/my-skill",
    repository_url="https://github.com/example/my-skill",
)
```

### 5. 版本管理

使用语义版本：

```
MAJOR.MINOR.PATCH
1.0.0 - Initial release
1.1.0 - New feature
1.0.1 - Bug fix
2.0.0 - Breaking changes
```

### 6. 依赖管理

明确声明依赖：

```python
metadata = SkillMetadata(
    dependencies={
        "text-processor": ">=1.0.0",
        "data-analyzer": "^2.0.0",
    }
)
```

---

## 常见问题

### Q: 如何处理长时间运行的技能？

A: 使用异步执行和适当的超时设置：

```python
metadata = SkillMetadata(
    timeout_seconds=600,  # 10 minutes
)
```

### Q: 如何在技能链中传递数据？

A: 使用输入/输出映射：

```python
ChainStep(
    skill_name="skill1",
    input_mapping={"param1": "source_field"},
    output_mapping={"result": "target_field"},
)
```

### Q: 如何处理技能依赖？

A: 在元数据中声明依赖，系统会自动验证：

```python
metadata = SkillMetadata(
    dependencies={"required-skill": ">=1.0.0"}
)
```

### Q: 如何调试技能执行？

A: 查看执行历史和日志：

```python
executor = get_skill_executor()
history = await executor.list_execution_history("my-skill", limit=10)
for context in history:
    print(context.to_dict())
```

### Q: 如何优化技能性能？

A:
1. 减少超时时间
2. 优化内存使用
3. 使用缓存
4. 异步处理
5. 批量操作

---

## 总结

X-Agent 技能系统提供了一个完整的、可扩展的技能管理和执行平台。通过遵循本文档的指南和最佳实践，您可以创建高质量、安全、高效的技能。

更多信息请访问: https://x-agent.example.com/docs
"""

# 技能系统文档
SKILL_SYSTEM_DOCUMENTATION = __doc__
