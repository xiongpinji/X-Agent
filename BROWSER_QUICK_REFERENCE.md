"""Quick Reference Card for Browser Enhancement Features."""

# X-Agent 浏览器能力增强 - 快速参考

## 模块速查表

### 1. 网络监控 (network_monitor.py)
```python
from backend.app.services.browser.network_monitor import NetworkMonitor

monitor = NetworkMonitor()
await monitor.start_monitoring(page)

# 获取请求
requests = monitor.get_requests(url_pattern="api/.*")

# 获取响应
responses = monitor.get_responses()

# 获取失败请求
failed = monitor.get_failed_requests()

# 获取摘要
summary = monitor.get_summary()
# {
#   "total_requests": 10,
#   "total_responses": 10,
#   "failed_responses": 1,
#   "total_duration_ms": 1234.5,
#   "average_response_time_ms": 123.45
# }

# 清除历史
monitor.clear_history()
```

### 2. 元素引用 (element_reference.py)
```python
from backend.app.services.browser.element_reference import ElementReferenceSystem

system = ElementReferenceSystem()

# 构建元素树
tree = await system.build_element_tree(page)
# tree.elements: {"ref_1": ElementReference, "ref_2": ...}

# 获取元素
elem = await system.get_element_by_ref("ref_1")
# {
#   "ref": "ref_1",
#   "tag_name": "button",
#   "element_type": "button",
#   "text": "Click me",
#   "visible": true,
#   "enabled": true
# }

# 点击元素
success = await system.click_by_ref("ref_1")

# 填充元素
success = await system.fill_by_ref("ref_2", "input value")
```

### 3. 控制台监控 (console_monitor.py)
```python
from backend.app.services.browser.console_monitor import ConsoleMonitor

monitor = ConsoleMonitor()
await monitor.start_monitoring(page)

# 获取所有消息
messages = monitor.get_messages()

# 获取错误
errors = monitor.get_errors()

# 获取警告
warnings = monitor.get_warnings()

# 按模式过滤
api_logs = monitor.get_messages(pattern=r"API.*")

# 获取摘要
summary = monitor.get_summary()
# {
#   "total_messages": 15,
#   "error_count": 2,
#   "warning_count": 3,
#   "log_count": 10,
#   "has_errors": true,
#   "has_warnings": true
# }

# 清除消息
monitor.clear_messages()
```

### 4. 自然语言定位 (natural_locator.py)
```python
from backend.app.services.browser.natural_locator import NaturalLocator

locator = NaturalLocator()

# 查找单个元素
element = await locator.find_element(page, "搜索按钮")
# {
#   "selector": "button[type='submit']",
#   "confidence": 0.95,
#   "reason": "text_match",
#   "text": "Search",
#   "tag_name": "button"
# }

# 查找多个元素
elements = await locator.find_elements(page, "登录", limit=5)
# [
#   {"selector": "...", "confidence": 0.98, ...},
#   {"selector": "...", "confidence": 0.85, ...},
#   ...
# ]
```

### 5. 页面快照 (page_snapshot.py)
```python
from backend.app.services.browser.page_snapshot import PageSnapshotManager

manager = PageSnapshotManager()

# 捕获快照
snapshot = await manager.capture_snapshot(
    page,
    label="before_action",
    include_accessibility=True
)

# 执行操作...

# 捕获后快照
snapshot_after = await manager.capture_snapshot(
    page,
    label="after_action"
)

# 比较快照
diff = manager.compare_snapshots(snapshot, snapshot_after)
# {
#   "dom_changed": true,
#   "title_changed": false,
#   "url_changed": false,
#   "error_count_increased": false
# }

# 获取DOM差异
dom_diff = manager.get_dom_diff("before_action", "after_action")
# ["--- before_action", "+++ after_action", ...]
```

### 6. 高级监控服务 (advanced_monitoring.py)
```python
from backend.app.services.browser.advanced_monitoring import advanced_browser_monitoring

# 创建会话
session = await advanced_browser_monitoring.create_session("session_1", page)

# 网络监控
requests = await advanced_browser_monitoring.get_network_requests("session_1")
summary = await advanced_browser_monitoring.get_network_summary("session_1")

# 元素引用
tree = await advanced_browser_monitoring.build_element_tree("session_1")
await advanced_browser_monitoring.click_by_ref("session_1", "ref_1")

# 控制台监控
errors = await advanced_browser_monitoring.get_console_errors("session_1")
summary = await advanced_browser_monitoring.get_console_summary("session_1")

# 自然语言定位
elements = await advanced_browser_monitoring.find_elements_by_description(
    "session_1",
    "搜索按钮",
    limit=5
)

# 页面快照
snapshot = await advanced_browser_monitoring.capture_snapshot(
    "session_1",
    label="test"
)

# 关闭会话
await advanced_browser_monitoring.close_session("session_1")
```

---

## API端点速查表

### 网络监控
```
POST /api/v1/browser/advanced/network/requests
POST /api/v1/browser/advanced/network/responses
POST /api/v1/browser/advanced/network/summary
POST /api/v1/browser/advanced/network/clear
```

### 元素引用
```
POST /api/v1/browser/advanced/elements/tree
POST /api/v1/browser/advanced/elements/{ref}
POST /api/v1/browser/advanced/elements/{ref}/click
POST /api/v1/browser/advanced/elements/{ref}/fill
```

### 控制台监控
```
POST /api/v1/browser/advanced/console/messages
POST /api/v1/browser/advanced/console/errors
POST /api/v1/browser/advanced/console/summary
POST /api/v1/browser/advanced/console/clear
```

### 自然语言定位
```
POST /api/v1/browser/advanced/elements/find
```

### 页面快照
```
POST /api/v1/browser/advanced/snapshot
POST /api/v1/browser/advanced/snapshot/compare
POST /api/v1/browser/advanced/snapshot/diff
```

---

## 常见用法模式

### 模式1: 监控页面加载
```python
# 开始监控
session = await advanced_browser_monitoring.create_session("s1", page)

# 导航
await page.goto("https://example.com")

# 获取网络统计
summary = await advanced_browser_monitoring.get_network_summary("s1")
print(f"加载了 {summary['total_requests']} 个请求")

# 检查错误
errors = await advanced_browser_monitoring.get_console_errors("s1")
if errors:
    print(f"发现 {len(errors)} 个错误")
```

### 模式2: 自动化表单填充
```python
# 构建元素树
tree = await advanced_browser_monitoring.build_element_tree("s1")

# 查找表单字段
elements = await advanced_browser_monitoring.find_elements_by_description(
    "s1",
    "用户名输入框",
    limit=1
)

if elements:
    # 通过选择器填充
    await page.fill(elements[0]['selector'], "username")

# 查找提交按钮
buttons = await advanced_browser_monitoring.find_elements_by_description(
    "s1",
    "提交按钮",
    limit=1
)

if buttons:
    await page.click(buttons[0]['selector'])
```

### 模式3: 页面变化检测
```python
# 捕获初始状态
await advanced_browser_monitoring.capture_snapshot("s1", label="initial")

# 执行操作
await page.click("button")
await page.wait_for_load_state("networkidle")

# 捕获最终状态
await advanced_browser_monitoring.capture_snapshot("s1", label="final")

# 比较
diff = await advanced_browser_monitoring.compare_snapshots(
    "s1",
    "initial",
    "final"
)

if diff['dom_changed']:
    print("页面内容已更改")
    
if diff['error_count_increased']:
    print("发现新的错误")
```

### 模式4: API调用监控
```python
# 获取所有API请求
api_requests = await advanced_browser_monitoring.get_network_requests(
    "s1",
    url_pattern=r"api/.*"
)

# 获取所有API响应
api_responses = await advanced_browser_monitoring.get_network_responses(
    "s1",
    url_pattern=r"api/.*"
)

# 分析
for resp in api_responses:
    if resp['status'] >= 400:
        print(f"API错误: {resp['status']} {resp['url']}")
```

---

## 性能优化建议

### 1. 定期清除历史
```python
# 每10个操作后清除一次
if operation_count % 10 == 0:
    await advanced_browser_monitoring.clear_network_history("s1")
    await advanced_browser_monitoring.clear_console_messages("s1")
```

### 2. 使用URL过滤
```python
# 只获取API请求，减少内存占用
api_requests = await advanced_browser_monitoring.get_network_requests(
    "s1",
    url_pattern=r"^https://api\..*"
)
```

### 3. 选择性快照
```python
# 只在关键点捕获快照
await advanced_browser_monitoring.capture_snapshot(
    "s1",
    label="critical_point",
    include_accessibility=False,  # 不需要时禁用
    include_network=False,
    include_console=False
)
```

### 4. 缓存元素树
```python
# 构建一次，多次使用
tree = await advanced_browser_monitoring.build_element_tree("s1")

# 重复使用tree中的ref
for ref in tree['elements']:
    elem = await advanced_browser_monitoring.get_element_by_ref("s1", ref)
```

---

## 错误处理

```python
try:
    session = await advanced_browser_monitoring.create_session("s1", page)
except KeyError as e:
    print(f"会话错误: {e}")
except Exception as e:
    print(f"未知错误: {e}")
finally:
    await advanced_browser_monitoring.close_session("s1")
```

---

## 调试技巧

### 1. 打印网络摘要
```python
summary = await advanced_browser_monitoring.get_network_summary("s1")
print(f"总请求: {summary['total_requests']}")
print(f"失败: {summary['failed_responses']}")
print(f"平均响应时间: {summary['average_response_time_ms']:.2f}ms")
```

### 2. 列出所有元素
```python
tree = await advanced_browser_monitoring.build_element_tree("s1")
for ref, elem in tree['elements'].items():
    print(f"{ref}: {elem['tag_name']} - {elem['text']}")
```

### 3. 检查控制台错误
```python
errors = await advanced_browser_monitoring.get_console_errors("s1")
for error in errors:
    print(f"错误: {error['text']}")
    if error['location']:
        print(f"位置: {error['location']}")
```

### 4. 查看DOM差异
```python
diff = await advanced_browser_monitoring.get_dom_diff("s1", "before", "after")
if diff:
    for line in diff[:20]:  # 显示前20行
        print(line)
```

---

## 文件位置

| 功能 | 文件 |
|------|------|
| 网络监控 | `backend/app/services/browser/network_monitor.py` |
| 元素引用 | `backend/app/services/browser/element_reference.py` |
| 控制台监控 | `backend/app/services/browser/console_monitor.py` |
| 自然语言定位 | `backend/app/services/browser/natural_locator.py` |
| 页面快照 | `backend/app/services/browser/page_snapshot.py` |
| 高级监控 | `backend/app/services/browser/advanced_monitoring.py` |
| API端点 | `backend/app/api/browser_advanced.py` |
| 测试 | `tests/test_browser_advanced.py` |
| 文档 | `BROWSER_ENHANCEMENT_GUIDE.md` |
| 示例 | `examples/browser_monitoring_examples.py` |

---

## 更多信息

- 详细文档: 见 `BROWSER_ENHANCEMENT_GUIDE.md`
- 使用示例: 见 `examples/browser_monitoring_examples.py`
- 完整总结: 见 `BROWSER_ENHANCEMENT_SUMMARY.md`
- 测试用例: 见 `tests/test_browser_advanced.py`
