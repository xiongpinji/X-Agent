"""Integration guide for advanced browser monitoring features."""

# X-Agent 浏览器能力增强集成指南

## 概述

本指南说明如何将新的浏览器监控和自动化功能集成到X-Agent项目中。

## 新增模块

### 1. 网络请求监控 (network_monitor.py)
- **功能**: 监听所有HTTP请求和响应
- **核心类**: `NetworkMonitor`, `NetworkRequest`, `NetworkResponse`
- **主要方法**:
  - `start_monitoring(page)` - 开始监控
  - `get_requests(url_pattern)` - 获取请求
  - `get_responses(url_pattern)` - 获取响应
  - `get_failed_requests()` - 获取失败请求
  - `get_summary()` - 获取摘要

### 2. 元素引用系统 (element_reference.py)
- **功能**: 为页面元素生成唯一引用ID
- **核心类**: `ElementReferenceSystem`, `ElementReference`, `ElementTree`
- **主要方法**:
  - `build_element_tree(page)` - 构建元素树
  - `get_element_by_ref(ref)` - 通过ref获取元素
  - `click_by_ref(ref)` - 通过ref点击
  - `fill_by_ref(ref, value)` - 通过ref填充

### 3. 控制台日志捕获 (console_monitor.py)
- **功能**: 捕获所有控制台消息
- **核心类**: `ConsoleMonitor`, `ConsoleMessageRecord`
- **主要方法**:
  - `start_monitoring(page)` - 开始监控
  - `get_messages(pattern, only_errors)` - 获取消息
  - `get_errors()` - 获取错误
  - `get_summary()` - 获取摘要

### 4. 自然语言定位 (natural_locator.py)
- **功能**: 使用自然语言描述定位元素
- **核心类**: `NaturalLocator`, `LocatedElement`
- **主要方法**:
  - `find_element(page, description)` - 查找单个元素
  - `find_elements(page, description, limit)` - 查找多个元素

### 5. 页面快照 (page_snapshot.py)
- **功能**: 捕获和比较页面状态
- **核心类**: `PageSnapshotManager`, `PageSnapshot`, `SnapshotDiff`
- **主要方法**:
  - `capture_snapshot(page, label)` - 捕获快照
  - `compare_snapshots(before, after)` - 比较快照
  - `get_dom_diff(before_label, after_label)` - 获取DOM差异

### 6. 高级监控服务 (advanced_monitoring.py)
- **功能**: 集成所有监控功能的统一服务
- **核心类**: `AdvancedBrowserMonitoring`, `AdvancedBrowserSession`
- **主要方法**: 见下文API部分

## API端点

所有端点都在 `/api/v1/browser/advanced` 前缀下。

### 网络监控
- `POST /network/requests` - 获取网络请求
- `POST /network/responses` - 获取网络响应
- `POST /network/summary` - 获取网络摘要
- `POST /network/clear` - 清除网络历史

### 元素引用
- `POST /elements/tree` - 构建元素树
- `POST /elements/{ref}` - 获取元素信息
- `POST /elements/{ref}/click` - 点击元素
- `POST /elements/{ref}/fill` - 填充元素

### 控制台监控
- `POST /console/messages` - 获取控制台消息
- `POST /console/errors` - 获取错误消息
- `POST /console/summary` - 获取摘要
- `POST /console/clear` - 清除消息

### 自然语言定位
- `POST /elements/find` - 通过描述查找元素

### 页面快照
- `POST /snapshot` - 捕获快照
- `POST /snapshot/compare` - 比较快照
- `POST /snapshot/diff` - 获取DOM差异

## 集成步骤

### 1. 注册API路由

在 `backend/app/web.py` 中添加：

```python
from backend.app.api import browser_advanced

app.include_router(browser_advanced.router)
```

### 2. 在现有浏览器服务中集成

修改 `backend/app/services/browser/automation.py`：

```python
from backend.app.services.browser.advanced_monitoring import advanced_browser_monitoring

class BrowserAutomationService:
    async def create_session_with_monitoring(self, **kwargs):
        # 创建基础会话
        session = self.create_session(**kwargs)
        
        # 创建高级监控会话
        if session.page:
            await advanced_browser_monitoring.create_session(
                session.session_id,
                session.page
            )
        
        return session
    
    async def close_session_with_monitoring(self, session_id: str):
        # 关闭高级监控
        await advanced_browser_monitoring.close_session(session_id)
        
        # 关闭基础会话
        return self.close_session(session_id)
```

### 3. 使用示例

```python
# 创建会话
session = await advanced_browser_monitoring.create_session("session_1", page)

# 构建元素树
tree = await advanced_browser_monitoring.build_element_tree("session_1")

# 通过自然语言查找元素
elements = await advanced_browser_monitoring.find_elements_by_description(
    "session_1",
    "搜索按钮",
    limit=5
)

# 获取网络请求
requests = await advanced_browser_monitoring.get_network_requests(
    "session_1",
    url_pattern="api/.*"
)

# 捕获快照
snapshot = await advanced_browser_monitoring.capture_snapshot(
    "session_1",
    label="before_action"
)

# 执行操作...

# 捕获后快照
snapshot_after = await advanced_browser_monitoring.capture_snapshot(
    "session_1",
    label="after_action"
)

# 比较快照
diff = await advanced_browser_monitoring.compare_snapshots(
    "session_1",
    "before_action",
    "after_action"
)

# 获取控制台错误
errors = await advanced_browser_monitoring.get_console_errors("session_1")

# 关闭会话
await advanced_browser_monitoring.close_session("session_1")
```

## 性能考虑

### 内存管理
- 网络监控会保存所有请求/响应头
- 对于长时间运行的会话，定期调用 `clear_network_history()` 和 `clear_console_messages()`
- 元素树构建会缓存所有元素引用，大型页面可能消耗大量内存

### 性能指标
- 网络监控开销: < 5%
- 元素树构建: < 500ms
- 控制台消息捕获延迟: < 10ms
- 自然语言定位: < 1s

### 优化建议
1. 使用URL模式过滤网络请求，减少内存占用
2. 定期清除历史数据
3. 对大型页面使用选择性元素树构建
4. 缓存自然语言定位结果

## 安全考虑

### 敏感数据过滤
- 网络监控会捕获请求/响应头，可能包含敏感信息
- 建议在生产环境中过滤敏感头（Authorization, Cookie等）
- 控制台消息可能包含用户数据，需要谨慎处理

### 实现敏感数据过滤

```python
SENSITIVE_HEADERS = {
    'authorization', 'cookie', 'x-api-key', 'x-auth-token'
}

def filter_headers(headers: dict) -> dict:
    return {
        k: v for k, v in headers.items()
        if k.lower() not in SENSITIVE_HEADERS
    }
```

## 测试

运行测试套件：

```bash
pytest tests/test_browser_advanced.py -v
```

测试覆盖：
- 网络监控准确性
- 元素引用系统
- 控制台捕获
- 自然语言定位
- 快照功能
- 端到端集成

## 故障排除

### 问题: 元素树构建缓慢
**解决**: 
- 减少选择器数量
- 使用更具体的选择器
- 对大型页面使用分页加载

### 问题: 内存占用过高
**解决**:
- 定期清除网络历史
- 清除控制台消息
- 关闭不需要的监控功能

### 问题: 自然语言定位不准确
**解决**:
- 使用更具体的描述
- 检查元素的ARIA标签
- 增加相似度阈值

## 未来改进

1. **LLM辅助定位**: 使用LLM改进自然语言元素定位
2. **性能优化**: 实现增量元素树更新
3. **高级过滤**: 支持更复杂的网络请求过滤
4. **可视化**: 添加元素树可视化工具
5. **录制回放**: 支持会话录制和回放

## 参考资源

- Playwright文档: https://playwright.dev/python/
- Chrome DevTools Protocol: https://chromedevtools.github.io/devtools-protocol/
- 无障碍树规范: https://www.w3.org/WAI/ARIA/apg/

## 支持

如有问题或建议，请提交Issue或PR。
