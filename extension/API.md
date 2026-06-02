# X-Agent Chrome Extension API 文档

## 目录

1. [Background Script API](#background-script-api)
2. [Content Script API](#content-script-api)
3. [MCP Protocol](#mcp-protocol)
4. [Storage API](#storage-api)
5. [Error Handling](#error-handling)

## Background Script API

### Session Management

#### `CREATE_SESSION`
创建新的浏览器自动化会话。

**请求**
```javascript
{
  type: 'CREATE_SESSION',
  payload: {
    sessionName: string,      // 会话名称
    traceId?: string,         // 追踪ID
    runId?: string            // 运行ID
  }
}
```

**响应**
```javascript
{
  success: boolean,
  session: {
    id: string,
    name: string,
    traceId: string,
    runId: string,
    createdAt: ISO8601,
    tabs: Array,
    actions: Array
  }
}
```

**示例**
```javascript
chrome.runtime.sendMessage({
  type: 'CREATE_SESSION',
  payload: {
    sessionName: '登录流程自动化',
    traceId: 'trace_123',
    runId: 'run_456'
  }
}, response => {
  if (response.success) {
    console.log('会话已创建:', response.session.id);
  }
});
```

### Element Operations

#### `GET_PAGE_ELEMENTS`
获取页面中匹配选择器的所有元素。

**请求**
```javascript
{
  type: 'GET_PAGE_ELEMENTS',
  payload: {
    selector: string,         // CSS选择器
    includeHidden?: boolean   // 是否包含隐藏元素
  }
}
```

**响应**
```javascript
{
  success: boolean,
  elements: Array<{
    refId: string,            // 元素引用ID
    tag: string,              // HTML标签
    text: string,             // 文本内容
    selector: string,         // CSS选择器
    visible: boolean,         // 是否可见
    rect: {                   // 位置和大小
      top: number,
      left: number,
      width: number,
      height: number
    }
  }>,
  count: number
}
```

**示例**
```javascript
chrome.runtime.sendMessage({
  type: 'GET_PAGE_ELEMENTS',
  payload: {
    selector: 'button, a, input',
    includeHidden: false
  }
}, response => {
  console.log(`找到 ${response.count} 个元素`);
  response.elements.forEach(el => {
    console.log(`${el.refId}: ${el.tag} - ${el.text}`);
  });
});
```

#### `GET_ELEMENT_REF`
为指定元素生成唯一引用ID。

**请求**
```javascript
{
  type: 'GET_ELEMENT_REF',
  payload: {
    selector: string          // CSS选择器
  }
}
```

**响应**
```javascript
{
  success: boolean,
  refId: string,              // ref_1, ref_2, ...
  data: {
    tag: string,
    id: string,
    className: string,
    text: string,
    value: string,
    rect: Object,
    visible: boolean,
    disabled: boolean,
    readonly: boolean,
    attributes: Object,
    styles: Object
  }
}
```

#### `CLICK_ELEMENT`
点击指定的页面元素。

**请求**
```javascript
{
  type: 'CLICK_ELEMENT',
  payload: {
    selector?: string,        // CSS选择器
    refId?: string            // 元素引用ID
  }
}
```

**响应**
```javascript
{
  success: boolean,
  clicked: boolean,
  error?: string
}
```

**示例**
```javascript
// 使用选择器
chrome.runtime.sendMessage({
  type: 'CLICK_ELEMENT',
  payload: { selector: '#submit-btn' }
}, response => {
  console.log('点击成功:', response.success);
});

// 使用引用ID
chrome.runtime.sendMessage({
  type: 'CLICK_ELEMENT',
  payload: { refId: 'ref_1' }
}, response => {
  console.log('点击成功:', response.success);
});
```

### Form Operations

#### `FILL_FORM`
填充表单字段。

**请求**
```javascript
{
  type: 'FILL_FORM',
  payload: {
    fields: Array<{
      selector?: string,      // CSS选择器
      refId?: string,         // 元素引用ID
      value: string,          // 要填充的值
      action?: 'set'|'append'|'replace'  // 填充方式
    }>
  }
}
```

**响应**
```javascript
{
  success: boolean,
  filled: number,             // 成功填充的字段数
  results: Array<{
    selector: string,
    success: boolean,
    error?: string
  }>
}
```

**示例**
```javascript
chrome.runtime.sendMessage({
  type: 'FILL_FORM',
  payload: {
    fields: [
      { selector: '#username', value: 'user@example.com' },
      { selector: '#password', value: 'password123' },
      { selector: '#remember', value: 'on' }
    ]
  }
}, response => {
  console.log(`成功填充 ${response.filled} 个字段`);
});
```

### Content Extraction

#### `EXTRACT_PAGE_CONTENT`
提取页面内容。

**请求**
```javascript
{
  type: 'EXTRACT_PAGE_CONTENT',
  payload: {
    includeText?: boolean,    // 包含文本
    includeLinks?: boolean,   // 包含链接
    includeImages?: boolean   // 包含图片
  }
}
```

**响应**
```javascript
{
  success: boolean,
  content: {
    url: string,
    title: string,
    text: string,
    links: Array<{
      text: string,
      href: string,
      title: string
    }>,
    images: Array<{
      src: string,
      alt: string,
      title: string
    }>,
    forms: Array<{
      id: string,
      name: string,
      action: string,
      method: string,
      fields: Array
    }>,
    metadata: Object
  }
}
```

### Tab Management

#### `GET_TAB_GROUPS`
获取所有标签组。

**请求**
```javascript
{
  type: 'GET_TAB_GROUPS'
}
```

**响应**
```javascript
{
  success: boolean,
  groups: Array<{
    id: number,
    title: string,
    color: string,
    collapsed: boolean,
    tabs: Array<{
      id: number,
      title: string,
      url: string,
      active: boolean,
      favIconUrl: string
    }>
  }>
}
```

#### `CREATE_TAB_GROUP`
创建新的标签组。

**请求**
```javascript
{
  type: 'CREATE_TAB_GROUP',
  payload: {
    title: string,            // 标签组名称
    color?: string,           // 颜色: blue, red, yellow, green, pink, purple, cyan
    tabs?: Array<number>      // 标签ID列表
  }
}
```

**响应**
```javascript
{
  success: boolean,
  group: {
    id: number,
    title: string,
    color: string,
    tabs: Array
  }
}
```

#### `NAVIGATE_TAB`
导航到指定URL。

**请求**
```javascript
{
  type: 'NAVIGATE_TAB',
  payload: {
    url: string               // 目标URL
  }
}
```

**响应**
```javascript
{
  success: boolean,
  url: string,
  error?: string
}
```

### Screenshot & Recording

#### `TAKE_SCREENSHOT`
截取当前页面。

**请求**
```javascript
{
  type: 'TAKE_SCREENSHOT',
  payload: {
    format?: 'png'|'jpeg',    // 图片格式
    quality?: number          // JPEG质量 (1-100)
  }
}
```

**响应**
```javascript
{
  success: boolean,
  dataUrl: string,            // Data URL格式的图片
  error?: string
}
```

#### `RECORD_ACTION`
记录用户操作。

**请求**
```javascript
{
  type: 'RECORD_ACTION',
  payload: {
    action: string,           // 操作类型
    details: Object           // 操作详情
  }
}
```

**响应**
```javascript
{
  success: boolean
}
```

## Content Script API

### Element Highlighting

#### `HIGHLIGHT_ELEMENTS`
高亮页面元素。

**请求**
```javascript
{
  type: 'HIGHLIGHT_ELEMENTS',
  selectors: Array<string>,   // CSS选择器数组
  color?: string,             // 高亮颜色 (十六进制)
  duration?: number           // 持续时间 (毫秒)
}
```

**响应**
```javascript
{
  success: boolean,
  highlighted: number         // 高亮的元素数量
}
```

### UI Control

#### `TOGGLE_SIDEBAR`
切换侧边栏显示。

**请求**
```javascript
{
  type: 'TOGGLE_SIDEBAR'
}
```

**响应**
```javascript
{
  success: boolean,
  visible: boolean
}
```

#### `TOGGLE_ELEMENT_HIGHLIGHT`
切换元素高亮模式。

**请求**
```javascript
{
  type: 'TOGGLE_ELEMENT_HIGHLIGHT'
}
```

**响应**
```javascript
{
  success: boolean,
  recording: boolean
}
```

## MCP Protocol

### Message Format

所有MCP消息遵循以下格式:

```javascript
{
  id: number,                 // 消息ID
  timestamp: ISO8601,         // 时间戳
  type: string,               // 消息类型
  payload?: Object,           // 消息负载
  error?: string              // 错误信息
}
```

### Connection Lifecycle

1. **初始化**
```javascript
{
  type: 'initialize',
  version: '1.0.0',
  capabilities: [...]
}
```

2. **心跳**
```javascript
{
  type: 'ping'
}
```

3. **断开连接**
```javascript
{
  type: 'disconnect'
}
```

## Storage API

### Session Storage

```javascript
// 保存会话
await storageManager.saveSession(session);

// 获取会话
const session = await storageManager.getSession();

// 清除会话
await storageManager.clearSession();
```

### Settings Storage

```javascript
// 保存设置
await storageManager.saveSettings({
  theme: 'dark',
  language: 'zh-CN'
});

// 获取设置
const settings = await storageManager.getSettings();
```

### History Storage

```javascript
// 添加到历史
await storageManager.addToHistory({
  type: 'click',
  selector: '#button'
});

// 获取历史
const history = await storageManager.getHistory(100);

// 清除历史
await storageManager.clearHistory();
```

### Cache Storage

```javascript
// 保存缓存
await storageManager.saveCache('key', value, ttl);

// 获取缓存
const value = await storageManager.getCache('key');

// 清除缓存
await storageManager.clearCache('key');
```

## Error Handling

### 错误代码

| 代码 | 描述 |
|------|------|
| 1001 | 元素未找到 |
| 1002 | 选择器无效 |
| 1003 | 操作超时 |
| 1004 | 权限被拒绝 |
| 1005 | 网络错误 |
| 2001 | MCP连接失败 |
| 2002 | 消息格式错误 |
| 2003 | 请求超时 |

### 错误处理示例

```javascript
chrome.runtime.sendMessage(request, response => {
  if (chrome.runtime.lastError) {
    console.error('通信错误:', chrome.runtime.lastError);
    return;
  }

  if (!response.success) {
    console.error('操作失败:', response.error);
    return;
  }

  console.log('操作成功:', response);
});
```

## 最佳实践

### 1. 错误处理
- 始终检查响应的success字段
- 实现重试逻辑
- 记录错误日志

### 2. 性能优化
- 批量操作而不是单个操作
- 使用元素引用而不是重复查询
- 清理不需要的监听器

### 3. 安全性
- 验证所有用户输入
- 不要在消息中传输敏感数据
- 使用HTTPS通信

### 4. 兼容性
- 检查浏览器版本
- 使用特性检测
- 提供降级方案
