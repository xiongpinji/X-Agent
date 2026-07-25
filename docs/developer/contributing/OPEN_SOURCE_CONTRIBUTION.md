# X-Agent 开源贡献指南

**版本**: 1.0.0  
**日期**: 2026-05-27  
**目标**: 指导开发者如何为X-Agent项目做出贡献

---

## 目录

1. [贡献类型](#贡献类型)
2. [开始贡献](#开始贡献)
3. [代码规范](#代码规范)
4. [提交规范](#提交规范)
5. [PR 流程](#pr-流程)
6. [Issue 模板](#issue-模板)
7. [代码审查](#代码审查)
8. [社区准则](#社区准则)

---

## 贡献类型

### 1. 代码贡献

#### 新功能开发

- 实现新的功能或能力
- 遵循项目架构和设计模式
- 包含完整的测试和文档

#### Bug 修复

- 修复已报告的问题
- 包含回归测试
- 更新相关文档

#### 性能优化

- 改进代码性能
- 提供性能基准
- 包含优化说明

#### 代码重构

- 改进代码质量
- 保持功能不变
- 包含重构说明

### 2. 文档贡献

#### 文档编写

- 编写新的文档
- 改进现有文档
- 修复文档错误

#### 示例代码

- 创建使用示例
- 编写教程
- 提供最佳实践

#### 翻译

- 翻译文档
- 翻译注释
- 本地化内容

### 3. 测试贡献

#### 单元测试

- 编写单元测试
- 提高代码覆盖率
- 测试边界情况

#### 集成测试

- 编写集成测试
- 测试组件交互
- 测试端到端流程

#### 性能测试

- 编写性能测试
- 基准测试
- 压力测试

### 4. 社区贡献

#### 问题回答

- 在GitHub Discussions中回答问题
- 在Discord中帮助他人
- 在论坛中分享知识

#### 代码审查

- 审查他人的PR
- 提供建设性反馈
- 帮助改进代码质量

#### 社区管理

- 组织社区活动
- 管理讨论
- 维护社区秩序

#### 推广

- 撰写博客文章
- 制作视频教程
- 在社交媒体上分享

---

## 开始贡献

### 1. Fork 项目

```bash
# 访问 GitHub 项目页面
# https://github.com/x-agent/x-agent-core

# 点击 "Fork" 按钮

# 克隆你的 fork
git clone https://github.com/YOUR_USERNAME/x-agent-core.git
cd x-agent-core

# 添加上游仓库
git remote add upstream https://github.com/x-agent/x-agent-core.git
```

### 2. 创建分支

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

### 3. 进行开发

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
ruff check --fix .
```

### 4. 提交更改

```bash
# 查看更改
git status

# 暂存更改
git add .

# 提交更改
git commit -m "feat: add new feature"

# 推送到你的 fork
git push origin feature/your-feature-name
```

### 5. 创建 Pull Request

- 访问你的 fork 页面
- 点击 "New Pull Request" 按钮
- 选择 base 分支为 `develop`
- 填写 PR 描述
- 点击 "Create Pull Request"

---

## 代码规范

### 1. Python 代码规范

#### 风格指南

遵循 PEP 8 风格指南：

```python
# 好的例子
def calculate_total(items: List[Item]) -> float:
    """计算总价"""
    total = 0.0
    for item in items:
        total += item.price * item.quantity
    return total

# 不好的例子
def calc_total(items):
    total=0.0
    for item in items:
        total+=item.price*item.quantity
    return total
```

#### 类型提示

使用类型提示提高代码质量：

```python
from typing import Dict, List, Optional, Any

def process_data(
    data: Dict[str, Any],
    filters: Optional[List[str]] = None
) -> Dict[str, Any]:
    """处理数据"""
    pass
```

#### 文档字符串

使用Google风格的文档字符串：

```python
def calculate_total(items: List[Item]) -> float:
    """
    计算项目总价
    
    Args:
        items: 项目列表
    
    Returns:
        总价
    
    Raises:
        ValueError: 如果项目列表为空
    
    Examples:
        >>> items = [Item(price=10, quantity=2)]
        >>> calculate_total(items)
        20.0
    """
    if not items:
        raise ValueError("Items list cannot be empty")
    
    return sum(item.price * item.quantity for item in items)
```

#### 错误处理

使用适当的异常处理：

```python
try:
    result = process_data(data)
except ValueError as e:
    logger.error(f"Invalid data: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

### 2. 代码质量工具

#### Black (代码格式化)

```bash
# 格式化代码
black .

# 检查格式
black --check .
```

#### Ruff (代码检查)

```bash
# 检查代码
ruff check .

# 自动修复
ruff check --fix .
```

#### Mypy (类型检查)

```bash
# 检查类型
mypy backend/
```

#### Pytest (测试)

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_plugin.py

# 生成覆盖率报告
pytest --cov=backend tests/
```

---

## 提交规范

### Conventional Commits

遵循 Conventional Commits 规范：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### 类型

- **feat**: 新功能
- **fix**: 修复bug
- **docs**: 文档更新
- **style**: 代码风格改变（不影响功能）
- **refactor**: 代码重构
- **perf**: 性能优化
- **test**: 测试相关
- **chore**: 构建、依赖等

#### 示例

```bash
# 新功能
git commit -m "feat(plugin): add plugin marketplace support"

# Bug修复
git commit -m "fix(workflow): resolve node execution timeout issue"

# 文档更新
git commit -m "docs: update plugin development guide"

# 性能优化
git commit -m "perf(memory): optimize vector search performance"

# 带body的提交
git commit -m "feat(api): add webhook support

- Implement webhook registration API
- Add webhook event dispatching
- Include webhook retry logic

Closes #123"
```

---

## PR 流程

### 1. PR 标题

清晰简洁的标题，遵循 Conventional Commits：

```
feat: add plugin marketplace support
fix: resolve workflow node timeout issue
docs: update API documentation
```

### 2. PR 描述

```markdown
## 描述
简要描述这个PR的目的和改变

## 相关Issue
Closes #123

## 改变类型
- [ ] Bug修复
- [ ] 新功能
- [ ] 破坏性改变
- [ ] 文档更新

## 测试
- [ ] 添加了新测试
- [ ] 所有测试通过
- [ ] 测试覆盖率 >= 80%

## 检查清单
- [ ] 代码遵循项目风格
- [ ] 自我审查了代码
- [ ] 添加了必要的注释
- [ ] 更新了相关文档
- [ ] 没有新的警告
- [ ] 添加了测试
- [ ] 测试通过

## 截图 (如果适用)
[添加截图]
```

### 3. PR 审查流程

```
提交PR
    ↓
自动检查 (CI/CD)
    ↓
代码审查
    ↓
请求更改或批准
    ↓
更新代码 (如需要)
    ↓
合并
```

### 4. 审查反馈

#### 接收反馈

- 保持开放心态
- 理解反馈的目的
- 提出问题以澄清

#### 回应反馈

```markdown
感谢你的反馈！我已经做了以下改进：

1. 改进了错误处理
2. 添加了更多测试
3. 更新了文档

请再次审查。
```

#### 更新代码

```bash
# 进行更改
# ...

# 提交更改
git add .
git commit -m "refactor: address review feedback"

# 推送更新
git push origin feature/your-feature-name
```

---

## Issue 模板

### Bug 报告

```markdown
## 问题描述
清晰简洁地描述问题

## 复现步骤
1. 步骤1
2. 步骤2
3. 步骤3

## 预期行为
应该发生什么

## 实际行为
实际发生了什么

## 环境信息
- X-Agent版本: 
- Python版本: 
- 操作系统: 

## 附加信息
日志、截图等
```

### 功能请求

```markdown
## 功能描述
描述你想要的功能

## 使用场景
这个功能解决什么问题

## 建议实现
你的实现建议 (可选)

## 替代方案
是否有其他解决方案

## 附加信息
其他相关信息
```

### 文档改进

```markdown
## 文档位置
指出需要改进的文档

## 问题描述
描述文档的问题

## 建议改进
你的改进建议

## 参考资源
相关资源链接
```

---

## 代码审查

### 审查要点

#### 功能正确性

- 代码是否实现了预期功能
- 是否处理了边界情况
- 是否有潜在的bug

#### 代码质量

- 代码是否易读易维护
- 是否遵循项目风格
- 是否有重复代码

#### 性能

- 是否有性能问题
- 是否有内存泄漏
- 是否有不必要的计算

#### 安全性

- 是否有安全漏洞
- 是否正确处理了输入
- 是否保护了敏感信息

#### 测试

- 是否有充分的测试
- 测试是否覆盖了主要场景
- 是否有边界情况测试

#### 文档

- 是否有适当的注释
- 是否更新了文档
- 是否有使用示例

### 审查反馈

#### 好的反馈

```markdown
这个实现很好，但我建议使用异步处理来提高性能。
你可以参考 `backend/app/core/async_handler.py` 中的示例。
```

#### 不好的反馈

```markdown
这个代码不好。
```

---

## 社区准则

### 1. 尊重

- 尊重所有社区成员
- 接受不同观点
- 避免人身攻击

### 2. 包容

- 欢迎多样性
- 支持新手
- 创建安全环境

### 3. 协作

- 共同解决问题
- 互相帮助
- 分享知识

### 4. 诚实

- 坦诚沟通
- 承认错误
- 透明决策

### 5. 专业

- 保持专业态度
- 避免垃圾信息
- 遵守规则

---

## 常见问题

### Q1: 我应该从哪里开始?

A: 查看 "good-first-issue" 标签的Issue，这些是适合新手的任务。

### Q2: 如何获得帮助?

A: 在GitHub Discussions中提问，或加入Discord社区。

### Q3: 我的PR被拒绝了怎么办?

A: 理解拒绝的原因，改进代码，重新提交。

### Q4: 需要多长时间才能合并PR?

A: 通常在1-2周内，取决于代码复杂度和审查者的可用性。

### Q5: 我可以同时处理多个PR吗?

A: 可以，但建议先完成一个再开始下一个。

---

## 贡献者权益

### 认可

- 在README中列出
- GitHub贡献者徽章
- 社区认可

### 权限

- 代码审查权限
- 发布权限
- 决策权

### 支持

- 优先支持
- 特殊咨询时间
- 职业发展机会

---

## 更多资源

- [社区建设计划](./COMMUNITY_BUILDING_PLAN.md)
- [行为准则](./CODE_OF_CONDUCT.md)
- [插件开发指南](../plugins/PLUGIN_DEVELOPMENT_GUIDE.md)
- [API 参考](../api/API_REFERENCE.md)

---

## 联系方式

- **邮件**: community@x-agent.io
- **Discord**: https://discord.gg/x-agent
- **论坛**: https://forum.x-agent.io
- **GitHub**: https://github.com/x-agent/x-agent-core

感谢你的贡献！

