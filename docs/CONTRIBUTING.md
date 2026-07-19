# X-Agent 贡献指南

**版本**: 1.0.0  
**最后更新**: 2026-05-27

---

## 目录

1. [如何贡献](#如何贡献)
2. [代码规范](#代码规范)
3. [提交规范](#提交规范)
4. [PR 流程](#pr-流程)
5. [Issue 模板](#issue-模板)
6. [代码审查流程](#代码审查流程)
7. [社区准则](#社区准则)

---

## 如何贡献

### 贡献类型

我们欢迎以下类型的贡献：

1. **代码贡献**
   - 新功能开发
   - Bug 修复
   - 性能优化
   - 代码重构

2. **文档贡献**
   - 文档编写
   - 示例代码
   - 教程
   - 翻译

3. **测试贡献**
   - 单元测试
   - 集成测试
   - 性能测试
   - 端到端测试

4. **社区贡献**
   - 问题回答
   - 代码审查
   - 社区管理
   - 推广

### 开始贡献

#### 1. Fork 项目

```bash
# 访问 GitHub 项目页面
# 点击 "Fork" 按钮

# 克隆你的 fork
git clone https://github.com/YOUR_USERNAME/x-agent-core.git
cd x-agent-core

# 添加上游仓库
git remote add upstream https://github.com/x-agent/x-agent-core.git
```

#### 2. 创建分支

```bash
# 更新本地 develop 分支
git fetch upstream
git checkout develop
git merge upstream/develop

# 创建功能分支
git checkout -b feature/your-feature-name

# 或修复分支
git checkout -b bugfix/issue-description

# 或文档分支
git checkout -b docs/documentation-update
```

#### 3. 进行开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 进行代码修改...

# 运行测试
pytest

# 检查代码风格
ruff check .
black --check .

# 格式化代码
black .
ruff check . --fix
```

#### 4. 提交更改

```bash
# 查看更改
git status
git diff

# 暂存更改
git add .

# 提交更改（遵循提交规范）
git commit -m "feat: add new feature

- Detailed description of changes
- Additional context if needed

Fixes #123"
```

#### 5. 推送和创建 PR

```bash
# 推送到你的 fork
git push origin feature/your-feature-name

# 在 GitHub 上创建 Pull Request
# - 填写 PR 标题和描述
# - 链接相关 Issue
# - 请求代码审查
```

---

## 代码规范

### Python 代码风格

遵循 PEP 8 标准，使用 Black 和 Ruff 进行格式化。

#### 命名规范

```python
# 类名：PascalCase
class WorkflowEngine:
    pass

# 函数名：snake_case
def execute_workflow():
    pass

# 常量：UPPER_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 300

# 私有方法：_leading_underscore
def _internal_method():
    pass

# 受保护方法：_leading_underscore
def _protected_method():
    pass
```

#### 文档字符串

```python
def execute_workflow(workflow_id: str, context: Dict) -> WorkflowRun:
    """
    执行工作流。
    
    这是一个更详细的描述，说明函数的功能和行为。
    
    Args:
        workflow_id: 工作流的唯一标识符
        context: 执行上下文，包含必要的参数和状态
    
    Returns:
        WorkflowRun: 工作流执行实例，包含执行结果和指标
    
    Raises:
        WorkflowNotFound: 当工作流不存在时抛出
        ExecutionError: 当执行失败时抛出
    
    Example:
        >>> run = await execute_workflow("wf_123", {})
        >>> print(run.status)
        'completed'
    """
    pass
```

#### 类型提示

```python
from typing import List, Dict, Optional, Union

def process_data(
    data: List[Dict[str, Any]],
    filter_key: Optional[str] = None,
    timeout: int = 300
) -> Union[List[Dict], None]:
    """处理数据"""
    pass
```

#### 导入顺序

```python
# 1. 标准库
import os
import sys
from typing import List, Dict

# 2. 第三方库
import numpy as np
from fastapi import FastAPI
from sqlalchemy import create_engine

# 3. 本地库
from backend.app.core.agent import Agent
from backend.app.services.memory import Memory
```

### 代码质量

#### 复杂度限制

- 函数复杂度 (Cyclomatic Complexity) < 10
- 函数长度 < 50 行
- 类方法数 < 20

#### 测试覆盖率

- 目标覆盖率 > 80%
- 关键路径 100% 覆盖
- 使用 `pytest --cov` 检查

#### 性能要求

- API 响应时间 < 1 秒
- 数据库查询 < 100ms
- 内存使用 < 500MB

---

## 提交规范

### Conventional Commits

遵循 Conventional Commits 规范：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### 类型

| 类型 | 描述 | 示例 |
|------|------|------|
| feat | 新功能 | feat: add agent execution |
| fix | Bug 修复 | fix: resolve memory leak |
| docs | 文档更新 | docs: update API guide |
| style | 代码风格 | style: format code |
| refactor | 代码重构 | refactor: simplify logic |
| perf | 性能优化 | perf: optimize query |
| test | 测试相关 | test: add unit tests |
| chore | 构建/依赖 | chore: update deps |
| ci | CI/CD 配置 | ci: add GitHub Actions |

### 提交示例

```bash
# 新功能
git commit -m "feat: add workflow retry mechanism

- Implement exponential backoff strategy
- Add configurable retry limits
- Add retry metrics tracking

Closes #456"

# Bug 修复
git commit -m "fix: resolve race condition in memory store

- Add proper locking mechanism
- Fix concurrent access issue
- Add test case

Fixes #789"

# 文档更新
git commit -m "docs: add deployment guide

- Add Docker deployment instructions
- Add Kubernetes setup guide
- Add troubleshooting section"
```

---

## PR 流程

### PR 标题

```
[TYPE] Brief description (< 70 characters)

Examples:
[FEATURE] Add workflow retry mechanism
[BUGFIX] Fix memory leak in agent engine
[DOCS] Update API documentation
[TEST] Add integration tests for workflows
```

### PR 描述模板

```markdown
## Description
简要描述你的更改

## Type of Change
- [ ] New feature
- [ ] Bug fix
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Related Issues
Fixes #123
Related to #456

## Changes Made
- 具体的更改 1
- 具体的更改 2
- 具体的更改 3

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally
- [ ] No breaking changes

## Screenshots (if applicable)
添加相关截图

## Additional Notes
任何其他需要说明的信息
```

### PR 审查标准

#### 代码质量
- [ ] 代码遵循项目规范
- [ ] 没有明显的 bug
- [ ] 逻辑清晰易懂
- [ ] 没有重复代码

#### 测试
- [ ] 有相应的测试
- [ ] 测试覆盖率足够
- [ ] 所有测试通过

#### 文档
- [ ] 代码有适当的注释
- [ ] 文档已更新
- [ ] API 文档已更新

#### 性能
- [ ] 没有性能回退
- [ ] 资源使用合理
- [ ] 查询优化

#### 安全
- [ ] 没有安全漏洞
- [ ] 输入验证充分
- [ ] 敏感数据处理正确

---

## Issue 模板

### Bug 报告

```markdown
## Description
清晰简洁地描述 bug

## Steps to Reproduce
1. 第一步
2. 第二步
3. 第三步

## Expected Behavior
应该发生什么

## Actual Behavior
实际发生了什么

## Environment
- OS: [e.g. Ubuntu 20.04]
- Python: [e.g. 3.11]
- X-Agent Version: [e.g. 1.0.0]

## Logs
```
粘贴相关日志
```

## Additional Context
任何其他相关信息
```

### 功能请求

```markdown
## Description
功能的清晰描述

## Motivation
为什么需要这个功能？

## Proposed Solution
你建议的解决方案

## Alternatives
你考虑过的其他方案

## Additional Context
任何其他相关信息
```

---

## 代码审查流程

### 审查者职责

1. **代码质量审查**
   - 检查代码风格
   - 验证逻辑正确性
   - 检查性能影响

2. **测试审查**
   - 验证测试覆盖率
   - 检查测试质量
   - 确保测试通过

3. **文档审查**
   - 检查文档完整性
   - 验证示例正确性
   - 检查 API 文档

4. **安全审查**
   - 检查安全漏洞
   - 验证输入验证
   - 检查敏感数据处理

### 审查意见

```markdown
# 代码审查意见

## 总体评价
这个 PR 看起来不错，有以下几点建议。

## 需要改进的地方

### 1. 性能问题
在第 45 行，这个查询可能很慢。建议添加索引。

```python
# 当前代码
result = db.query(Agent).filter(Agent.status == 'active').all()

# 建议改进
# 添加索引后会更快
```

### 2. 代码风格
第 78 行的函数太长了，建议拆分。

## 建议的改进

- 添加更多的错误处理
- 增加日志记录
- 添加类型提示

## 批准条件

- [ ] 解决所有评论
- [ ] 添加相应的测试
- [ ] 更新文档
```

---

## 社区准则

### 行为准则

我们致力于为所有贡献者提供一个包容、尊重的环境。

#### 我们期望的行为

- 使用包容性语言
- 尊重不同的观点
- 接受建设性批评
- 关注社区最佳利益
- 对其他社区成员表示同情

#### 不可接受的行为

- 骚扰、歧视或骚扰
- 人身攻击或侮辱性评论
- 发布他人的私人信息
- 其他不专业的行为

### 执行

违反行为准则的行为将由项目维护者处理。可能的后果包括：

- 警告
- 临时禁言
- 永久禁言

### 报告问题

如果你目睹或经历了不可接受的行为，请通过以下方式报告：

- 发送邮件至 conduct@x-agent.dev
- 在 GitHub 上私下联系维护者

---

## 开发工作流

### 日常开发

```bash
# 1. 同步上游代码
git fetch upstream
git rebase upstream/develop

# 2. 进行开发
# ... 编写代码 ...

# 3. 运行测试
pytest

# 4. 检查代码质量
ruff check .
black --check .
mypy backend/

# 5. 提交更改
git add .
git commit -m "feat: ..."

# 6. 推送到 fork
git push origin feature/...

# 7. 创建 PR
# 在 GitHub 上创建 PR
```

### 处理审查意见

```bash
# 1. 拉取最新的 PR 分支
git fetch origin
git checkout feature/...

# 2. 进行修改
# ... 编写代码 ...

# 3. 提交修改
git add .
git commit -m "refactor: address review comments"

# 4. 推送更新
git push origin feature/...

# PR 会自动更新
```

### 合并 PR

```bash
# 1. 确保分支是最新的
git fetch upstream
git rebase upstream/develop

# 2. 解决任何冲突
# ... 解决冲突 ...

# 3. 推送更新
git push origin feature/...

# 4. 等待维护者合并
# 或者如果你有权限，可以自己合并
```

---

## 获取帮助

- **文档**: [完整文档](README.md)
- **讨论区**: [GitHub Discussions](https://github.com/x-agent/x-agent-core/discussions)
- **邮件**: contribute@x-agent.dev
- **Slack**: [加入我们的 Slack](https://x-agent.slack.com)

---

**X-Agent 贡献指南** - 欢迎加入我们的社区
