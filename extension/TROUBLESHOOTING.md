# X-Agent Chrome Extension 故障排除指南

## 目录

1. [连接问题](#连接问题)
2. [功能问题](#功能问题)
3. [性能问题](#性能问题)
4. [安全问题](#安全问题)
5. [调试技巧](#调试技巧)

## 连接问题

### 问题：扩展无法连接到桌面应用

**症状**
- 弹出窗口显示"未连接"
- 操作返回连接错误
- 无法创建会话

**诊断步骤**

1. **检查桌面应用状态**
```bash
# 检查X-Agent进程
ps aux | grep x-agent

# 检查监听端口
netstat -an | grep LISTEN
```

2. **检查Native Messaging Host**
```bash
# Windows
reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.xagent.extension"

# macOS
cat ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.xagent.extension.json

# Linux
cat ~/.config/google-chrome/NativeMessagingHosts/com.xagent.extension.json
```

3. **查看浏览器日志**
```bash
# Chrome日志位置
# Windows: %LOCALAPPDATA%\Google\Chrome\User Data\chrome_debug.log
# macOS: ~/Library/Application Support/Google/Chrome/chrome_debug.log
# Linux: ~/.config/google-chrome/chrome_debug.log
```

**解决方案**

1. **重启桌面应用**
```bash
# 停止应用
pkill -f x-agent

# 重新启动
x-agent-desktop
```

2. **重新安装Native Messaging Host**
```bash
# Windows
python scripts/install_native_host.py

# macOS/Linux
python3 scripts/install_native_host.py
```

3. **检查权限**
```bash
# 确保host脚本可执行
chmod +x /path/to/native-host

# 检查Chrome扩展ID
# 打开 chrome://extensions/ 查看ID
```

4. **重新加载扩展**
- 打开 `chrome://extensions/`
- 找到X-Agent扩展
- 点击刷新按钮

### 问题：连接频繁断开

**症状**
- 操作中途连接断开
- 需要频繁重新连接
- 超时错误

**诊断步骤**

1. **检查网络连接**
```bash
# 测试本地连接
ping localhost

# 检查端口连接
telnet localhost 9000
```

2. **查看错误日志**
- 打开 `chrome://extensions/` → 背景页面
- 查看控制台错误

3. **检查系统资源**
```bash
# 检查内存使用
free -h  # Linux
vm_stat  # macOS
```

**解决方案**

1. **增加超时时间**
```javascript
// 在mcp-client.js中修改
const timeout = 60000; // 增加到60秒
```

2. **启用自动重连**
```javascript
// 已在mcp-client.js中实现
// 检查reconnectAttempts配置
this.maxReconnectAttempts = 5;
this.reconnectDelay = 1000;
```

3. **检查防火墙**
```bash
# Windows
netsh advfirewall show allprofiles

# macOS
sudo pfctl -s all

# Linux
sudo ufw status
```

## 功能问题

### 问题：元素选择器不工作

**症状**
- 获取元素返回空结果
- 点击/填充操作失败
- 选择器错误

**诊断步骤**

1. **验证选择器语法**
```javascript
// 在浏览器控制台测试
document.querySelectorAll('button')  // 应该返回元素列表
document.querySelector('#my-id')     // 应该返回单个元素
```

2. **检查元素是否存在**
```javascript
// 检查DOM中是否存在元素
const element = document.querySelector('selector');
console.log(element);  // 应该不是null
```

3. **检查元素可见性**
```javascript
// 检查元素是否可见
const element = document.querySelector('selector');
console.log(element.offsetParent !== null);  // 应该是true
```

**解决方案**

1. **使用正确的选择器**
```javascript
// 错误
'button'  // 可能太宽泛

// 正确
'button.submit-btn'  // 更具体
'#submit-button'     // 使用ID
'form input[type="submit"]'  // 使用属性
```

2. **等待元素加载**
```javascript
// 使用waitForElement
chrome.runtime.sendMessage({
  type: 'WAIT_ELEMENT',
  payload: {
    selector: '#dynamic-element',
    timeout: 5000
  }
});
```

3. **使用元素引用**
```javascript
// 先获取引用，再使用
chrome.runtime.sendMessage({
  type: 'GET_ELEMENT_REF',
  payload: { selector: 'button' }
}, response => {
  // 使用 response.refId
});
```

### 问题：表单填充失败

**症状**
- 字段值未更新
- 验证错误
- 事件未触发

**诊断步骤**

1. **检查字段类型**
```javascript
// 检查表单字段
const input = document.querySelector('#field');
console.log(input.type);      // 字段类型
console.log(input.disabled);  // 是否禁用
console.log(input.readOnly);  // 是否只读
```

2. **检查字段可访问性**
```javascript
// 检查字段是否可交互
const input = document.querySelector('#field');
console.log(input.offsetParent !== null);  // 是否可见
console.log(input.style.display !== 'none');  // 是否隐藏
```

3. **测试手动填充**
```javascript
// 手动测试
const input = document.querySelector('#field');
input.value = 'test value';
input.dispatchEvent(new Event('input', { bubbles: true }));
input.dispatchEvent(new Event('change', { bubbles: true }));
```

**解决方案**

1. **使用正确的字段选择器**
```javascript
// 确保选择器指向正确的字段
chrome.runtime.sendMessage({
  type: 'FILL_FORM',
  payload: {
    fields: [
      { selector: '#username', value: 'user@example.com' },
      { selector: '#password', value: 'password123' }
    ]
  }
});
```

2. **处理特殊字段类型**
```javascript
// Select字段
{ selector: 'select#country', value: 'US' }

// Checkbox
{ selector: 'input[type="checkbox"]', value: 'on' }

// Radio
{ selector: 'input[type="radio"][value="option1"]', value: 'on' }

// Textarea
{ selector: 'textarea#comments', value: 'My comment' }
```

3. **添加延迟**
```javascript
// 某些表单需要延迟处理
chrome.runtime.sendMessage({
  type: 'FILL_FORM',
  payload: {
    fields: [
      { selector: '#field1', value: 'value1' },
      { selector: '#field2', value: 'value2', delay: 500 }
    ]
  }
});
```

### 问题：内容提取不完整

**症状**
- 缺少文本内容
- 链接或图片未提取
- 表单信息不完整

**诊断步骤**

1. **检查页面加载状态**
```javascript
// 检查页面是否完全加载
console.log(document.readyState);  // 应该是'complete'
```

2. **检查动态内容**
```javascript
// 某些内容可能通过JavaScript动态加载
// 等待加载完成
setTimeout(() => {
  // 提取内容
}, 2000);
```

3. **检查隐藏元素**
```javascript
// 某些元素可能被隐藏
const element = document.querySelector('selector');
console.log(window.getComputedStyle(element).display);
```

**解决方案**

1. **等待页面加载**
```javascript
chrome.runtime.sendMessage({
  type: 'EXTRACT_PAGE_CONTENT',
  payload: {
    includeText: true,
    includeLinks: true,
    includeImages: true,
    waitForLoad: true,
    timeout: 5000
  }
});
```

2. **包含隐藏元素**
```javascript
chrome.runtime.sendMessage({
  type: 'GET_PAGE_ELEMENTS',
  payload: {
    selector: '*',
    includeHidden: true  // 包含隐藏元素
  }
});
```

3. **处理动态内容**
```javascript
// 等待特定元素加载
chrome.runtime.sendMessage({
  type: 'WAIT_ELEMENT',
  payload: {
    selector: '.dynamic-content',
    timeout: 10000
  }
}, response => {
  if (response.success) {
    // 现在提取内容
    chrome.runtime.sendMessage({
      type: 'EXTRACT_PAGE_CONTENT',
      payload: { includeText: true }
    });
  }
});
```

## 性能问题

### 问题：扩展运行缓慢

**症状**
- 操作响应慢
- UI卡顿
- 高CPU使用率

**诊断步骤**

1. **检查内存使用**
```javascript
// 在background.js中
if (performance.memory) {
  console.log('内存使用:', performance.memory.usedJSHeapSize / 1048576, 'MB');
}
```

2. **检查事件监听器**
```javascript
// 查看是否有过多监听器
getEventListeners(document)  // Chrome DevTools命令
```

3. **性能分析**
```javascript
// 测量操作性能
performance.mark('operation-start');
// 执行操作
performance.mark('operation-end');
performance.measure('operation', 'operation-start', 'operation-end');
console.log(performance.getEntriesByName('operation')[0].duration);
```

**解决方案**

1. **清理历史记录**
```javascript
// 限制历史记录大小
const maxHistorySize = 100;
if (history.length > maxHistorySize) {
  history = history.slice(-maxHistorySize);
}
```

2. **优化DOM操作**
```javascript
// 使用DocumentFragment批量更新
const fragment = document.createDocumentFragment();
elements.forEach(el => {
  fragment.appendChild(el);
});
container.appendChild(fragment);
```

3. **移除不需要的监听器**
```javascript
// 及时移除监听器
element.removeEventListener('click', handler);
```

### 问题：内存泄漏

**症状**
- 内存占用持续增加
- 浏览器变慢
- 最终崩溃

**诊断步骤**

1. **使用Chrome DevTools**
   - 打开 `chrome://extensions/` → 背景页面
   - 打开DevTools → Memory标签
   - 拍摄堆快照
   - 比较多个快照找出泄漏

2. **检查事件监听器**
```javascript
// 查看是否有未移除的监听器
getEventListeners(window)
```

3. **检查定时器**
```javascript
// 确保清理定时器
clearInterval(intervalId);
clearTimeout(timeoutId);
```

**解决方案**

1. **正确清理资源**
```javascript
// 在卸载时清理
window.addEventListener('beforeunload', () => {
  // 移除监听器
  document.removeEventListener('click', handler);
  // 清理定时器
  clearInterval(intervalId);
  // 清理缓存
  cache.clear();
});
```

2. **使用WeakMap存储元素**
```javascript
// 使用WeakMap避免内存泄漏
const elementRefs = new WeakMap();
elementRefs.set(element, refId);
```

3. **定期清理缓存**
```javascript
// 限制缓存大小
const MAX_CACHE_SIZE = 1000;
if (cache.size > MAX_CACHE_SIZE) {
  const firstKey = cache.keys().next().value;
  cache.delete(firstKey);
}
```

## 安全问题

### 问题：权限被拒绝

**症状**
- 操作返回权限错误
- 无法访问某些功能
- 用户收到权限提示

**诊断步骤**

1. **检查manifest权限**
```json
// 查看manifest.json中的权限
{
  "permissions": [
    "activeTab",
    "scripting",
    "storage"
  ]
}
```

2. **检查host权限**
```json
{
  "host_permissions": [
    "<all_urls>"
  ]
}
```

**解决方案**

1. **请求必要权限**
```javascript
// 动态请求权限
chrome.permissions.request({
  permissions: ['storage'],
  origins: ['https://example.com/*']
}, granted => {
  if (granted) {
    console.log('权限已授予');
  }
});
```

2. **处理权限拒绝**
```javascript
// 优雅处理权限拒绝
try {
  // 尝试操作
} catch (error) {
  if (error.message.includes('permission')) {
    console.log('权限被拒绝，请在扩展设置中授予权限');
  }
}
```

### 问题：数据泄露风险

**症状**
- 敏感数据在日志中可见
- 数据未加密存储
- 通信未加密

**诊断步骤**

1. **检查日志输出**
```bash
# 搜索敏感数据
grep -r "password\|token\|secret" logs/
```

2. **检查存储数据**
```javascript
// 查看存储的数据
chrome.storage.local.get(null, items => {
  console.log(items);  // 检查是否包含敏感数据
});
```

**解决方案**

1. **加密敏感数据**
```javascript
// 使用加密库
const encrypted = CryptoJS.AES.encrypt(sensitiveData, key).toString();
chrome.storage.local.set({ encrypted });
```

2. **移除日志中的敏感数据**
```javascript
// 不要记录敏感信息
console.log('用户登录成功');  // 正确
console.log('用户登录:', password);  // 错误
```

3. **使用HTTPS通信**
```javascript
// 确保所有通信都使用HTTPS
const url = 'https://api.example.com/endpoint';
```

## 调试技巧

### 启用详细日志

```javascript
// 在background.js中
const DEBUG = true;

function log(message, data) {
  if (DEBUG) {
    console.log(`[X-Agent] ${message}`, data);
  }
}
```

### 使用Chrome DevTools

1. **打开背景页面DevTools**
   - `chrome://extensions/` → X-Agent → 背景页面

2. **打开Content Script DevTools**
   - 在网页上右键 → 检查 → Sources标签

3. **使用断点调试**
   - 在代码行号点击设置断点
   - 执行操作触发断点
   - 逐步执行代码

### 导出日志

```javascript
// 导出所有日志
const logs = [];
const originalLog = console.log;
console.log = function(...args) {
  logs.push(args);
  originalLog.apply(console, args);
};

// 导出为JSON
const logsJson = JSON.stringify(logs);
console.save = function(filename) {
  const blob = new Blob([logsJson], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
};
```

### 性能分析

```javascript
// 使用Performance API
performance.mark('start');
// 执行操作
performance.mark('end');
performance.measure('operation', 'start', 'end');

// 查看结果
const measure = performance.getEntriesByName('operation')[0];
console.log(`耗时: ${measure.duration}ms`);
```

## 获取帮助

如果以上解决方案都不能解决问题，请：

1. **收集诊断信息**
   - 浏览器版本
   - 扩展版本
   - 错误日志
   - 重现步骤

2. **提交问题**
   - GitHub Issues: https://github.com/x-agent/x-agent-core/issues
   - 邮件: support@x-agent.example.com

3. **联系支持**
   - 官网: https://x-agent.example.com
   - 文档: https://docs.x-agent.example.com
