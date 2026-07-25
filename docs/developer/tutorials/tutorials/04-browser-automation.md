# 浏览器自动化教程

学习如何使用 X-Agent 的浏览器自动化功能进行网页交互和数据提取。

## 目录

1. [浏览器自动化基础](#浏览器自动化基础)
2. [页面导航](#页面导航)
3. [元素交互](#元素交互)
4. [数据提取](#数据提取)
5. [高级功能](#高级功能)
6. [最佳实践](#最佳实践)

## 浏览器自动化基础

### 初始化浏览器

```python
from backend.app.core.browser import BrowserManager

# 创建浏览器管理器
browser_manager = BrowserManager()

# 启动浏览器
browser = await browser_manager.launch(
    headless=True,  # 无头模式
    browser_type="chromium",  # 浏览器类型
    viewport={"width": 1920, "height": 1080}
)

# 创建新页面
page = await browser.new_page()
```

### 关闭浏览器

```python
# 关闭页面
await page.close()

# 关闭浏览器
await browser.close()
```

## 页面导航

### 基础导航

```python
# 访问网页
await page.goto("https://example.com")

# 等待页面加载完成
await page.wait_for_load_state("networkidle")

# 获取页面标题
title = await page.title()
print(f"页面标题: {title}")

# 获取页面 URL
url = page.url
print(f"当前 URL: {url}")
```

### 页面刷新和返回

```python
# 刷新页面
await page.reload()

# 返回上一页
await page.go_back()

# 前进到下一页
await page.go_forward()
```

### 等待条件

```python
# 等待特定元素出现
await page.wait_for_selector("button.submit")

# 等待特定函数返回真
await page.wait_for_function("() => document.readyState === 'complete'")

# 等待导航完成
async with page.expect_navigation():
    await page.click("a.next-page")

# 等待弹窗
async with page.expect_popup() as popup_info:
    await page.click("button.open-popup")
popup = await popup_info.value
```

## 元素交互

### 定位元素

```python
# 使用 CSS 选择器定位
element = await page.query_selector("button.submit")

# 使用 XPath 定位
element = await page.query_selector("xpath=//button[@class='submit']")

# 使用文本定位
element = await page.query_selector("text=提交")

# 定位多个元素
elements = await page.query_selector_all("div.item")
```

### 点击和输入

```python
# 点击元素
await page.click("button.submit")

# 双击元素
await page.dblclick("div.item")

# 右键点击
await page.click("button.menu", button="right")

# 输入文本
await page.fill("input.search", "搜索关键词")

# 清空输入框
await page.fill("input.search", "")

# 追加文本
await page.type("input.search", "追加文本")
```

### 表单操作

```python
# 选择下拉框选项
await page.select_option("select.category", "electronics")

# 勾选复选框
await page.check("input.agree")

# 取消勾选
await page.uncheck("input.agree")

# 提交表单
await page.press("input.search", "Enter")
```

### 鼠标和键盘操作

```python
# 鼠标悬停
await page.hover("button.menu")

# 鼠标移动
await page.mouse.move(100, 100)

# 鼠标点击
await page.mouse.click(100, 100)

# 键盘按键
await page.press("input", "Tab")
await page.press("input", "Control+A")
await page.press("input", "Delete")

# 键盘输入
await page.keyboard.type("Hello World")
```

### 拖拽操作

```python
# 拖拽元素
await page.drag_and_drop("div.source", "div.target")

# 或使用鼠标操作
await page.mouse.move(100, 100)
await page.mouse.down()
await page.mouse.move(200, 200)
await page.mouse.up()
```

## 数据提取

### 获取元素属性

```python
# 获取文本内容
text = await page.text_content("div.title")

# 获取 HTML 内容
html = await page.inner_html("div.content")

# 获取属性值
href = await page.get_attribute("a.link", "href")

# 获取输入框的值
value = await page.input_value("input.search")
```

### 提取表格数据

```python
# 提取表格数据
table_data = await page.evaluate("""
    () => {
        const rows = document.querySelectorAll('table tbody tr');
        return Array.from(rows).map(row => {
            const cells = row.querySelectorAll('td');
            return Array.from(cells).map(cell => cell.textContent);
        });
    }
""")

print(table_data)
```

### 提取列表数据

```python
# 提取列表数据
items = await page.evaluate("""
    () => {
        const items = document.querySelectorAll('div.item');
        return Array.from(items).map(item => ({
            title: item.querySelector('.title').textContent,
            price: item.querySelector('.price').textContent,
            url: item.querySelector('a').href
        }));
    }
""")

for item in items:
    print(f"标题: {item['title']}")
    print(f"价格: {item['price']}")
    print(f"链接: {item['url']}")
```

### 执行 JavaScript

```python
# 执行 JavaScript 代码
result = await page.evaluate("() => 1 + 1")
print(result)  # 输出: 2

# 执行复杂的 JavaScript
data = await page.evaluate("""
    () => {
        return {
            title: document.title,
            url: window.location.href,
            cookies: document.cookie
        };
    }
""")

print(data)
```

## 高级功能

### 截图和录制

```python
# 截图
await page.screenshot(path="screenshot.png")

# 截图特定区域
await page.screenshot(
    path="area.png",
    clip={"x": 0, "y": 0, "width": 100, "height": 100}
)

# 录制视频
video_path = await page.video.path()
print(f"视频保存在: {video_path}")
```

### 处理弹窗和对话框

```python
# 处理 alert 弹窗
page.once("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
await page.click("button.alert")

# 处理 confirm 弹窗
page.once("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
await page.click("button.confirm")

# 处理 prompt 弹窗
page.once("dialog", lambda dialog: asyncio.create_task(dialog.accept("输入内容")))
await page.click("button.prompt")
```

### 处理文件上传

```python
# 设置文件上传
await page.set_input_files("input[type='file']", "path/to/file.txt")

# 或使用多个文件
await page.set_input_files("input[type='file']", [
    "path/to/file1.txt",
    "path/to/file2.txt"
])
```

### 处理下载

```python
# 等待下载
async with page.expect_download() as download_info:
    await page.click("a.download")

download = await download_info.value
await download.save_as("downloaded_file.pdf")
```

### 网络拦截

```python
# 拦截请求
async def handle_route(route):
    if "ads" in route.request.url:
        await route.abort()
    else:
        await route.continue_()

await page.route("**/*", handle_route)

# 修改请求
async def modify_route(route):
    headers = route.request.headers
    headers["User-Agent"] = "Custom User Agent"
    await route.continue_(headers=headers)

await page.route("**/*", modify_route)

# 模拟响应
async def mock_route(route):
    await route.abort(error_code="failed")

await page.route("**/api/data", mock_route)
```

### 处理 Cookie 和存储

```python
# 获取 Cookie
cookies = await browser.context.cookies()

# 设置 Cookie
await browser.context.add_cookies([
    {
        "name": "session_id",
        "value": "abc123",
        "url": "https://example.com"
    }
])

# 清除 Cookie
await browser.context.clear_cookies()

# 获取本地存储
storage = await page.evaluate("() => JSON.stringify(localStorage)")

# 设置本地存储
await page.evaluate("""
    () => {
        localStorage.setItem('key', 'value');
    }
""")
```

## 最佳实践

### 1. 错误处理

```python
try:
    await page.goto("https://example.com", timeout=30000)
except Exception as e:
    print(f"导航失败: {e}")
    # 重试或使用备用 URL
```

### 2. 等待策略

```python
# 等待特定元素加载
await page.wait_for_selector("div.content", timeout=10000)

# 等待网络空闲
await page.wait_for_load_state("networkidle")

# 等待特定条件
await page.wait_for_function(
    "() => document.querySelectorAll('div.item').length > 0"
)
```

### 3. 性能优化

```python
# 禁用图片加载以提高速度
await page.route("**/*.{png,jpg,jpeg,gif,svg}", lambda route: route.abort())

# 设置视口大小
await page.set_viewport_size({"width": 1920, "height": 1080})

# 使用无头模式
browser = await browser_manager.launch(headless=True)
```

### 4. 数据提取最佳实践

```python
# 使用 evaluate 而不是逐个查询元素
# 不推荐
for i in range(100):
    text = await page.text_content(f"div.item:nth-child({i})")

# 推荐
items = await page.evaluate("""
    () => {
        return Array.from(document.querySelectorAll('div.item'))
            .map(item => item.textContent);
    }
""")
```

## 完整示例：网页爬虫

```python
import asyncio
from backend.app.core.browser import BrowserManager

async def scrape_products():
    browser_manager = BrowserManager()
    browser = await browser_manager.launch()
    page = await browser.new_page()
    
    try:
        # 访问网站
        await page.goto("https://example.com/products")
        await page.wait_for_load_state("networkidle")
        
        # 提取产品数据
        products = await page.evaluate("""
            () => {
                return Array.from(document.querySelectorAll('div.product')).map(product => ({
                    name: product.querySelector('.name').textContent,
                    price: product.querySelector('.price').textContent,
                    url: product.querySelector('a').href
                }));
            }
        """)
        
        # 处理分页
        while True:
            # 检查是否有下一页
            next_button = await page.query_selector("a.next")
            if not next_button:
                break
            
            # 点击下一页
            await next_button.click()
            await page.wait_for_load_state("networkidle")
            
            # 提取下一页的数据
            more_products = await page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('div.product')).map(product => ({
                        name: product.querySelector('.name').textContent,
                        price: product.querySelector('.price').textContent,
                        url: product.querySelector('a').href
                    }));
                }
            """)
            
            products.extend(more_products)
        
        return products
        
    finally:
        await browser.close()

# 运行爬虫
products = asyncio.run(scrape_products())
for product in products:
    print(f"产品: {product['name']}, 价格: {product['price']}")
```

## 下一步

- 阅读 [最佳实践](../../best-practices/best-practices/README.md)
- 阅读 [故障排除](../../../operations/support/troubleshooting/COMMON_ISSUES.md)
- 探索 [示例代码库](../../examples/)
