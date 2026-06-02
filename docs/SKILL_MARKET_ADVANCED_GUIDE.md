"""技能市场高级功能使用示例和集成指南"""

# 技能市场高级功能 - 使用示例和集成指南

## 目录

1. [快速开始](#快速开始)
2. [版本管理示例](#版本管理示例)
3. [评论评分示例](#评论评分示例)
4. [搜索优化示例](#搜索优化示例)
5. [依赖管理示例](#依赖管理示例)
6. [更新管理示例](#更新管理示例)
7. [集成指南](#集成指南)
8. [最佳实践](#最佳实践)

---

## 快速开始

### 安装依赖

```bash
pip install fastapi pydantic python-dateutil
```

### 初始化管理器

```python
from backend.app.core.skill_version_manager import get_skill_version_manager
from backend.app.core.skill_review_system import get_skill_review_system
from backend.app.core.skill_search_engine import get_skill_search_engine
from backend.app.core.skill_dependency_manager import get_skill_dependency_manager
from backend.app.core.skill_update_manager import get_skill_update_manager

# 获取全局实例
version_mgr = get_skill_version_manager()
review_sys = get_skill_review_system()
search_engine = get_skill_search_engine()
dep_mgr = get_skill_dependency_manager()
update_mgr = get_skill_update_manager()
```

---

## 版本管理示例

### 示例1: 创建和管理版本

```python
# 创建新版本
success, error, version = version_mgr.create_version(
    skill_id="python-helper",
    version="1.0.0",
    changes="Initial release with basic Python assistance",
    compatibility="compatible",
    breaking_changes=[],
    migration_guide="",
)

if success:
    print(f"版本 {version.version} 创建成功")
else:
    print(f"创建失败: {error}")

# 创建下一个版本
success, error, version = version_mgr.create_version(
    skill_id="python-helper",
    version="1.1.0",
    changes="Added advanced debugging features",
    compatibility="compatible",
    breaking_changes=[],
)

# 获取所有版本
versions = version_mgr.get_versions("python-helper")
for v in versions:
    print(f"版本 {v.version}: {v.changes}")

# 获取当前版本
current = version_mgr.get_current_version("python-helper")
print(f"当前版本: {current.version}")

# 比较两个版本
success, error, comparison = version_mgr.compare_versions(
    "python-helper", "1.1.0", "1.0.0"
)
if success:
    print(f"1.1.0 是否更新: {comparison['v1_newer']}")
    print(f"破坏性变更: {comparison['v1_breaking_changes']}")

# 版本回滚
success, error = version_mgr.rollback_version("python-helper", "1.0.0")
if success:
    print("已回滚到版本 1.0.0")
```

### 示例2: 处理版本兼容性

```python
from backend.app.core.skill_version_manager import VersionCompatibility

# 创建有破坏性变更的版本
success, error, version = version_mgr.create_version(
    skill_id="data-analyzer",
    version="2.0.0",
    changes="Major refactoring with new API",
    compatibility=VersionCompatibility.BREAKING_CHANGE,
    breaking_changes=[
        "Changed analyze() method signature",
        "Removed deprecated functions",
        "New configuration format required",
    ],
    migration_guide="""
    # 迁移指南 v1.x -> v2.0

    ## 方法签名变更
    旧: analyze(data, options)
    新: analyze(data, config=None)

    ## 配置格式
    旧: {"mode": "fast"}
    新: {"performance": {"mode": "fast"}}

    ## 已移除的函数
    - analyze_legacy()
    - get_old_format()
    """,
)

# 检查兼容性
success, error, compat_info = version_mgr.check_compatibility(
    "data-analyzer", "1.5.0", "2.0.0"
)
if success:
    print(f"是否升级: {compat_info['is_upgrade']}")
    print(f"破坏性变更: {compat_info['breaking_changes']}")
    print(f"需要迁移: {compat_info['requires_migration']}")
    print(f"迁移指南:\n{compat_info['migration_guide']}")
```

---

## 评论评分示例

### 示例1: 添加和管理评论

```python
# 用户添加评论
success, error, review = review_sys.add_review(
    skill_id="python-helper",
    user_id="user123",
    user_name="Alice",
    rating=5,
    title="Excellent Python Assistant",
    comment="This skill has greatly improved my Python coding efficiency. Highly recommended!",
    verified_purchase=True,
)

if success:
    print(f"评论已添加，ID: {review.id}")
    print(f"状态: {review.status.value} (待审核)")
else:
    print(f"添加失败: {error}")

# 获取评论列表
reviews = review_sys.get_reviews(
    skill_id="python-helper",
    limit=10,
    sort_by="helpful",
)

for review in reviews:
    print(f"★{'★' * (review.rating - 1)} - {review.title}")
    print(f"  {review.comment}")
    print(f"  有用: {review.helpful_count}, 无用: {review.unhelpful_count}")

# 获取平均评分
avg_rating = review_sys.get_average_rating("python-helper")
distribution = review_sys.get_rating_distribution("python-helper")

print(f"平均评分: {avg_rating}/5.0")
print(f"评分分布:")
for rating, count in distribution.items():
    print(f"  {rating}星: {count}条评论")
```

### 示例2: 评论审核和举报

```python
from backend.app.core.skill_review_system import ReportReason

# 获取待审核评论
pending_reviews = review_sys.get_pending_reviews(limit=20)
for review in pending_reviews:
    print(f"待审核: {review.title} (by {review.user_name})")

# 批准评论
success, error = review_sys.approve_review(review.id)
if success:
    print("评论已批准")

# 拒绝评论
success, error = review_sys.reject_review(review.id)
if success:
    print("评论已拒绝")

# 举报不当评论
success, error, report = review_sys.report_review(
    review_id=review.id,
    reporter_id="user456",
    reason=ReportReason.SPAM,
    description="This review contains promotional content",
)

if success:
    print(f"举报已提交，ID: {report.id}")

# 处理举报
reports = review_sys.get_reports(status="pending")
for report in reports:
    print(f"举报: {report.reason.value} - {report.description}")
    
    # 隐藏评论
    success, error = review_sys.resolve_report(report.id, "hide")
    if success:
        print("评论已隐藏")
```

---

## 搜索优化示例

### 示例1: 索引和搜索

```python
# 索引技能
search_engine.index_skill(
    skill_id="python-helper",
    name="Python Helper",
    name_zh="Python助手",
    description="Advanced Python programming assistant with debugging and optimization",
    description_zh="高级Python编程助手，支持调试和优化",
    keywords=["python", "programming", "debugging", "optimization", "code"],
    category="development",
    tags=["coding", "automation", "productivity"],
)

# 执行搜索
results = search_engine.search(
    query="python debugging",
    filters={"category": "development"},
    limit=10,
)

print(f"找到 {len(results)} 个结果:")
for result in results:
    print(f"  {result.name_zh} (相关性: {result.relevance_score:.2f})")
    print(f"    匹配类型: {result.match_type}")
    print(f"    匹配字段: {', '.join(result.matched_fields)}")
```

### 示例2: 搜索建议

```python
# 获取搜索建议
suggestions = search_engine.get_suggestions("py", limit=10)
print("搜索建议:")
for suggestion in suggestions:
    print(f"  - {suggestion}")

# 获取热门搜索
popular = search_engine._get_popular_searches(limit=5)
print("热门搜索:")
for query in popular:
    print(f"  - {query}")

# 获取搜索统计
stats = search_engine.get_search_stats()
print(f"搜索统计:")
print(f"  总搜索次数: {stats['total_searches']}")
print(f"  唯一查询: {stats['unique_queries']}")
print(f"  已索引技能: {stats['indexed_skills']}")
print(f"  缓存大小: {stats['cache_size']}")
```

---

## 依赖管理示例

### 示例1: 声明和管理依赖

```python
from backend.app.core.skill_dependency_manager import DependencyType

# 添加必需依赖
success, error = dep_mgr.add_dependency(
    skill_id="advanced-python",
    dep_skill_id="python-helper",
    version_spec=">=1.0.0",
    dep_type=DependencyType.REQUIRED,
)

# 添加可选依赖
success, error = dep_mgr.add_dependency(
    skill_id="advanced-python",
    dep_skill_id="performance-optimizer",
    version_spec="*",
    dep_type=DependencyType.OPTIONAL,
)

# 获取依赖列表
deps = dep_mgr.get_dependencies("advanced-python")
for dep in deps:
    print(f"依赖: {dep.dep_skill_id}@{dep.version_spec} ({dep.dep_type.value})")

# 获取必需依赖
required = dep_mgr.get_required_dependencies("advanced-python")
print(f"必需依赖数: {len(required)}")

# 获取依赖此技能的技能
dependents = dep_mgr.get_dependents("python-helper")
print(f"依赖此技能的技能: {dependents}")
```

### 示例2: 依赖树和冲突检测

```python
# 构建依赖树
tree = dep_mgr.get_dependency_tree("advanced-python")
print("依赖树:")
print(dep_mgr.visualize_dependency_tree("advanced-python"))

# 检查依赖是否满足
dep_mgr.installed_skills["python-helper"] = "1.0.0"
success, error, missing = dep_mgr.check_dependencies("advanced-python")
if success:
    print("所有依赖已满足")
else:
    print(f"缺少依赖: {missing}")

# 解决冲突
success, error, conflicts = dep_mgr.resolve_conflicts([
    "skill1", "skill2", "skill3"
])
if not success:
    print(f"检测到 {len(conflicts)} 个冲突:")
    for conflict in conflicts:
        print(f"  类型: {conflict.conflict_type.value}")
        print(f"  描述: {conflict.description}")
        print(f"  建议: {conflict.resolution_suggestions}")
```

---

## 更新管理示例

### 示例1: 检查和安装更新

```python
from backend.app.core.skill_update_manager import UpdatePriority

# 注册可用更新
update_mgr.installed_versions["python-helper"] = "1.0.0"
success, error = update_mgr.register_available_update(
    skill_id="python-helper",
    current_version="1.0.0",
    new_version="1.1.0",
    changelog="Bug fixes and performance improvements",
    priority=UpdatePriority.MEDIUM,
    breaking_changes=[],
)

# 检查更新
success, error, update = update_mgr.check_updates("python-helper")
if success and update:
    print(f"有可用更新: {update.current_version} -> {update.new_version}")
    print(f"优先级: {update.priority.value}")
    print(f"更新日志: {update.changelog}")

# 安装更新
success, error, update = update_mgr.update_skill(
    skill_id="python-helper",
    new_version="1.1.0",
    user_id="user123",
)
if success:
    print(f"更新完成: {update.status.value}")
```

### 示例2: 自动更新和通知

```python
# 启用自动更新
success, error = update_mgr.enable_auto_update("python-helper")
if success:
    print("已启用自动更新")

# 检查是否启用
is_enabled = update_mgr.is_auto_update_enabled("python-helper")
print(f"自动更新已启用: {is_enabled}")

# 创建更新通知
update = update_mgr.available_updates.get("python-helper")
if update:
    success, error, notification = update_mgr.create_notification(
        skill_id="python-helper",
        user_id="user123",
        update=update,
    )

# 获取用户通知
notifications = update_mgr.get_notifications(
    user_id="user123",
    unread_only=True,
    limit=10,
)
print(f"未读通知: {len(notifications)}")

for notif in notifications:
    print(f"  {notif.update.skill_id}: {notif.update.new_version}")

# 标记为已读
if notifications:
    success, error = update_mgr.mark_notification_as_read(notifications[0].id)

# 获取统计
stats = update_mgr.get_update_stats()
print(f"更新统计:")
print(f"  可用更新: {stats['available_updates']}")
print(f"  严重更新: {stats['critical_updates']}")
print(f"  已安装更新: {stats['total_updates_installed']}")
```

---

## 集成指南

### 集成到FastAPI应用

```python
from fastapi import FastAPI
from backend.app.api.skill_market_advanced import router

app = FastAPI()

# 注册高级功能路由
app.include_router(router)

# 启动应用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 集成到现有技能市场

```python
from backend.app.core.skill_market_manager import get_skill_market_manager
from backend.app.core.skill_version_manager import get_skill_version_manager
from backend.app.core.skill_review_system import get_skill_review_system

class EnhancedSkillMarketManager:
    """增强的技能市场管理器"""
    
    def __init__(self):
        self.base_manager = get_skill_market_manager()
        self.version_mgr = get_skill_version_manager()
        self.review_sys = get_skill_review_system()
    
    async def publish_skill_with_version(self, skill, version_info):
        """发布技能并创建版本"""
        # 添加技能
        await self.base_manager.add_skill(skill)
        
        # 创建版本
        success, error, version = self.version_mgr.create_version(
            skill_id=skill.id,
            version=version_info["version"],
            changes=version_info["changes"],
        )
        
        return success, error
    
    async def get_skill_with_reviews(self, skill_id):
        """获取技能及其评论"""
        skill = await self.base_manager.get_skill_info(skill_id)
        reviews = self.review_sys.get_reviews(skill_id)
        avg_rating = self.review_sys.get_average_rating(skill_id)
        
        return {
            "skill": skill,
            "reviews": reviews,
            "average_rating": avg_rating,
        }
```

---

## 最佳实践

### 1. 版本管理

```python
# ✓ 好的做法
# 使用语义化版本
version_mgr.create_version("skill", "1.0.0", "Initial release")
version_mgr.create_version("skill", "1.1.0", "Bug fixes")
version_mgr.create_version("skill", "2.0.0", "Major refactoring")

# ✗ 避免
# 使用非标准版本号
version_mgr.create_version("skill", "v1", "Release")
version_mgr.create_version("skill", "1.0", "Update")
```

### 2. 评论管理

```python
# ✓ 好的做法
# 定期审核待审核评论
pending = review_sys.get_pending_reviews(limit=50)
for review in pending:
    if is_appropriate(review):
        review_sys.approve_review(review.id)
    else:
        review_sys.reject_review(review.id)

# ✗ 避免
# 自动批准所有评论
for review in pending:
    review_sys.approve_review(review.id)
```

### 3. 搜索优化

```python
# ✓ 好的做法
# 定期更新索引
for skill in all_skills:
    search_engine.index_skill(
        skill_id=skill.id,
        name=skill.name,
        name_zh=skill.name_zh,
        description=skill.description,
        description_zh=skill.description_zh,
        keywords=skill.keywords,
        category=skill.category,
        tags=skill.tags,
    )

# ✗ 避免
# 只索引部分字段
search_engine.index_skill(
    skill_id=skill.id,
    name=skill.name,
    # 缺少其他字段
)
```

### 4. 依赖管理

```python
# ✓ 好的做法
# 明确指定版本要求
dep_mgr.add_dependency("skill1", "skill2", ">=1.0.0")
dep_mgr.add_dependency("skill1", "skill3", "1.x")

# ✗ 避免
# 使用过于宽松的版本规范
dep_mgr.add_dependency("skill1", "skill2", "*")
```

### 5. 更新管理

```python
# ✓ 好的做法
# 为严重更新创建通知
if update.priority == UpdatePriority.CRITICAL:
    update_mgr.create_notification(skill_id, user_id, update)

# ✗ 避免
# 为所有更新创建通知
for update in all_updates:
    update_mgr.create_notification(skill_id, user_id, update)
```

---

## 性能优化建议

1. **缓存搜索结果**: 使用 `search_engine.search_cache` 缓存热门查询
2. **批量操作**: 使用批量API而不是逐个操作
3. **异步处理**: 对于长时间运行的操作使用异步任务
4. **定期清理**: 定期清理过期的缓存和通知

---

## 故障排除

### 问题1: 循环依赖错误

```python
# 问题
dep_mgr.add_dependency("skill1", "skill2")
dep_mgr.add_dependency("skill2", "skill1")  # 错误!

# 解决方案
# 重构技能架构，移除循环依赖
dep_mgr.add_dependency("skill1", "skill2")
dep_mgr.add_dependency("skill2", "skill3")
```

### 问题2: 版本冲突

```python
# 问题
dep_mgr.add_dependency("skill1", "base", "1.0.0")
dep_mgr.add_dependency("skill2", "base", "2.0.0")

# 解决方案
# 使用兼容的版本规范
dep_mgr.add_dependency("skill1", "base", ">=1.0.0")
dep_mgr.add_dependency("skill2", "base", ">=1.0.0")
```

---

## 相关资源

- [API文档](./SKILL_MARKET_ADVANCED_API.md)
- [测试套件](../tests/test_skill_market_advanced.py)
- [源代码](../backend/app/core/)
