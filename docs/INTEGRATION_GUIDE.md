"""
Integration guide for enhanced browser automation modules.
"""

INTEGRATION_GUIDE = """
# X-Agent 浏览器自动化增强 - 集成指南

## 快速开始

### 1. 安装依赖

```bash
# 确保已安装 Playwright
pip install playwright

# 安装浏览器驱动
playwright install chromium firefox
```

### 2. 导入模块

```python
from backend.app.services.browser.enhanced_service import EnhancedBrowserAutomationService
from backend.app.services.browser.smart_locator import SmartLocator
from backend.app.services.browser.waiter import SmartWaiter
from backend.app.services.browser.interactions import AdvancedInteractions
from backend.app.services.browser.analyzer import PageAnalyzer
from backend.app.services.browser.recovery import ErrorRecovery
from backend.app.services.browser.pool import create_browser_pool
from backend.app.services.browser.stealth import StealthBrowser
```

### 3. 创建服务实例

```python
# 创建增强自动化服务
service = EnhancedBrowserAutomationService(
    pool_size=5,
    default_timeout=30.0,
    enable_stealth=True,
)
```

## 集成场景

### 场景 1: 替换现有的基础自动化服务

**现有代码**:
```python
from backend.app.services.browser.automation import browser_automation

result = browser_automation.click(session_id, selector)
```

**迁移后**:
```python
from backend.app.services.browser.enhanced_service import get_enhanced_automation_service

service = get_enhanced_automation_service()
success = await service.find_and_click(session_id, selector)
```

**优势**:
- 自动重试和错误恢复
- 智能等待
- 更高的成功率

### 场景 2: 添加到现有的 API 端点

**现有端点**:
```python
@app.post("/api/browser/click")
async def click_element(session_id: str, selector: str):
    result = browser_automation.click(session_id, selector)
    return {"success": result.ok}
```

**增强后**:
```python
@app.post("/api/browser/click")
async def click_element(session_id: str, selector: str):
    service = get_enhanced_automation_service()
    success = await service.find_and_click(session_id, selector)
    
    # 获取详细统计
    stats = service.get_session_stats(session_id)
    
    return {
        "success": success,
        "stats": stats,
    }
```

### 场景 3: 集成到现有的自动化工作流

**现有工作流**:
```python
async def automate_task(url: str, actions: List[Dict]):
    session = browser_sessions.create()
    
    try:
        browser_automation.goto(session.session_id, url)
        
        for action in actions:
            if action["type"] == "click":
                browser_automation.click(session.session_id, action["selector"])
            elif action["type"] == "fill":
                browser_automation.fill(session.session_id, action["selector"], action["value"])
        
        return {"success": True}
    finally:
        browser_sessions.close(session.session_id)
```

**增强后**:
```python
async def automate_task(url: str, actions: List[Dict]):
    service = get_enhanced_automation_service()
    
    # 创建浏览器会话
    from playwright.async_api import async_playwright
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    
    session = await service.create_session("task_session", page)
    
    try:
        # 导航
        await service.navigate(session.session_id, url)
        
        # 执行操作
        for action in actions:
            if action["type"] == "click":
                await service.find_and_click(session.session_id, action["selector"])
            elif action["type"] == "fill":
                await service.find_and_fill(
                    session.session_id,
                    action["selector"],
                    action["value"],
                )
        
        # 获取统计
        stats = service.get_session_stats(session.session_id)
        
        return {
            "success": True,
            "stats": stats,
        }
    finally:
        await service.cleanup()
```

### 场景 4: 添加到现有的爬虫系统

**现有爬虫**:
```python
class WebScraper:
    def __init__(self):
        self.browser_automation = browser_automation
    
    async def scrape(self, url: str):
        session = browser_sessions.create()
        
        try:
            self.browser_automation.goto(session.session_id, url)
            content = self.browser_automation.extract_text(session.session_id, "body")
            return content
        finally:
            browser_sessions.close(session.session_id)
```

**增强后**:
```python
class EnhancedWebScraper:
    def __init__(self):
        self.service = get_enhanced_automation_service()
    
    async def scrape(self, url: str):
        from playwright.async_api import async_playwright
        
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        session = await self.service.create_session("scrape_session", page)
        
        try:
            # 导航
            await self.service.navigate(session.session_id, url)
            
            # 分析页面
            structure = await self.service.analyze_page(session.session_id)
            
            # 提取数据
            content = await self.service.extract_text(session.session_id, "body")
            
            return {
                "content": content,
                "structure": structure,
                "stats": self.service.get_session_stats(session.session_id),
            }
        finally:
            await self.service.cleanup()
```

## 模块化集成

### 仅使用特定模块

如果只需要特定功能，可以单独使用各个模块:

#### 仅使用智能定位器

```python
from backend.app.services.browser.smart_locator import SmartLocator

locator = SmartLocator("session_1")

# 查找元素
result = locator.find_element(
    css_selector=".button",
    fallback_to_ai=True,
)

if result.found:
    print(f"Element found: {result.strategy_used}")
```

#### 仅使用智能等待

```python
from backend.app.services.browser.waiter import SmartWaiter, WaitStrategy

waiter = SmartWaiter("session_1")

# 等待元素
result = await waiter.wait_for_selector(
    page,
    ".dynamic-content",
    strategy=WaitStrategy.ADAPTIVE,
)

if result.success:
    print(f"Element appeared after {result.time_taken_ms}ms")
```

#### 仅使用高级交互

```python
from backend.app.services.browser.interactions import AdvancedInteractions

interactions = AdvancedInteractions("session_1")

# 拖拽操作
result = await interactions.drag_and_drop(
    page,
    ".source",
    ".target",
)

# 文件上传
result = await interactions.upload_file(
    page,
    "input[type='file']",
    "/path/to/file",
)
```

#### 仅使用页面分析

```python
from backend.app.services.browser.analyzer import PageAnalyzer

analyzer = PageAnalyzer("session_1")

# 分析页面
structure = await analyzer.analyze_page(page)

print(f"Buttons: {len(structure.buttons)}")
print(f"Forms: {len(structure.forms)}")
print(f"Links: {len(structure.links)}")
```

#### 仅使用错误恢复

```python
from backend.app.services.browser.recovery import ErrorRecovery

recovery = ErrorRecovery("session_1")

# 检测 CAPTCHA
has_captcha = await recovery.detect_captcha(page)

# 检测登录要求
login_required = await recovery.detect_login_required(page)

# 重试操作
result = await recovery.retry_operation(
    operation,
    max_retries=3,
    backoff=True,
)
```

#### 仅使用浏览器池

```python
from backend.app.services.browser.pool import create_browser_pool

pool = create_browser_pool("main", max_browsers=5)

# 获取浏览器
browser = await pool.acquire_browser()

# 使用浏览器...

# 释放浏览器
await pool.release_browser(browser.browser_id)

# 获取统计
stats = pool.get_stats()
```

#### 仅使用反检测

```python
from backend.app.services.browser.stealth import StealthBrowser

stealth = StealthBrowser("session_1")

# 获取反检测选项
context_options = stealth.get_stealth_context_options()
launch_options = stealth.get_stealth_launch_options()

# 创建浏览器
browser = await playwright.chromium.launch(**launch_options)
context = await browser.new_context(**context_options)
page = await context.new_page()

# 应用反检测措施
await stealth.apply_stealth_measures(page)
```

## 与现有系统的兼容性

### 保持向后兼容

现有的 `browser_automation` 服务仍然可用:

```python
from backend.app.services.browser.automation import browser_automation

# 旧 API 仍然有效
result = browser_automation.click(session_id, selector)
```

### 逐步迁移策略

1. **第一阶段**: 新功能使用增强服务
   ```python
   # 新功能
   service = get_enhanced_automation_service()
   
   # 旧功能
   browser_automation.click(session_id, selector)
   ```

2. **第二阶段**: 关键功能迁移
   ```python
   # 迁移关键路径
   await service.find_and_click(session_id, selector)
   ```

3. **第三阶段**: 完全替换
   ```python
   # 所有功能使用增强服务
   service = get_enhanced_automation_service()
   ```

## 配置和环境变量

### 环境变量配置

```bash
# .env 文件
BROWSER_POOL_SIZE=5
BROWSER_DEFAULT_TIMEOUT=30
BROWSER_ENABLE_STEALTH=true
BROWSER_HEADLESS=true

LOCATOR_MAX_RETRIES=3
LOCATOR_RETRY_DELAY_MS=500

WAITER_DEFAULT_TIMEOUT=30
WAITER_ADAPTIVE_TIMEOUT=true

POOL_MAX_BROWSERS=5
POOL_IDLE_TIMEOUT=60

STEALTH_ENABLED=true
```

### Python 配置

```python
import os

# 从环境变量读取配置
pool_size = int(os.getenv("BROWSER_POOL_SIZE", "5"))
default_timeout = float(os.getenv("BROWSER_DEFAULT_TIMEOUT", "30.0"))
enable_stealth = os.getenv("BROWSER_ENABLE_STEALTH", "true").lower() == "true"

# 创建服务
service = EnhancedBrowserAutomationService(
    pool_size=pool_size,
    default_timeout=default_timeout,
    enable_stealth=enable_stealth,
)
```

## 监控和日志

### 启用详细日志

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

# 设置浏览器自动化日志级别
logging.getLogger('backend.app.services.browser').setLevel(logging.DEBUG)
```

### 收集指标

```python
# 定期收集统计信息
stats = service.get_session_stats(session_id)

# 记录到监控系统
monitoring.record({
    "action_count": stats["action_count"],
    "error_count": stats["error_count"],
    "uptime": stats["uptime"],
})

# 获取池统计
pool_stats = service.get_pool_stats()
for pool_id, stats in pool_stats.items():
    monitoring.record({
        "pool_id": pool_id,
        "active_browsers": stats["active_browsers"],
        "idle_browsers": stats["idle_browsers"],
    })
```

## 测试集成

### 单元测试

```python
import pytest
from backend.app.services.browser.enhanced_service import EnhancedBrowserAutomationService

@pytest.mark.asyncio
async def test_enhanced_automation():
    service = EnhancedBrowserAutomationService()
    
    # 测试代码
    assert service is not None
```

### 集成测试

```python
@pytest.mark.asyncio
async def test_complete_workflow():
    service = EnhancedBrowserAutomationService()
    
    from playwright.async_api import async_playwright
    
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    
    try:
        session = await service.create_session("test_session", page)
        
        # 测试导航
        await service.navigate(session.session_id, "https://example.com")
        
        # 测试交互
        await service.find_and_click(session.session_id, "button")
        
        # 验证
        stats = service.get_session_stats(session.session_id)
        assert stats["action_count"] > 0
    finally:
        await service.cleanup()
```

## 故障排除

### 导入错误

如果遇到导入错误:

```python
# 确保路径正确
import sys
sys.path.insert(0, '/path/to/X-Agent')

from backend.app.services.browser.enhanced_service import EnhancedBrowserAutomationService
```

### 依赖缺失

```bash
# 安装所有依赖
pip install playwright pytest pytest-asyncio
```

### 浏览器驱动缺失

```bash
# 安装浏览器驱动
playwright install chromium
playwright install firefox
```

## 性能调优

### 对于高速自动化

```python
service = EnhancedBrowserAutomationService(
    pool_size=10,
    default_timeout=15.0,
    enable_stealth=False,  # 禁用反检测以提高速度
)
```

### 对于可靠自动化

```python
service = EnhancedBrowserAutomationService(
    pool_size=3,
    default_timeout=60.0,
    enable_stealth=True,
)
```

### 对于受保护网站

```python
service = EnhancedBrowserAutomationService(
    pool_size=2,
    default_timeout=45.0,
    enable_stealth=True,
)
```

## 总结

集成增强浏览器自动化模块的步骤:

1. ✅ 安装依赖 (Playwright)
2. ✅ 导入模块
3. ✅ 创建服务实例
4. ✅ 替换或增强现有代码
5. ✅ 配置环境变量
6. ✅ 启用日志和监控
7. ✅ 编写测试
8. ✅ 部署和验证

通过这些步骤，可以平稳地将增强的浏览器自动化能力集成到 X-Agent 系统中。
"""

if __name__ == "__main__":
    print(INTEGRATION_GUIDE)
