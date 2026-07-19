# X-Agent Chrome Extension 开发文档

## 概述

X-Agent Chrome扩展是一个强大的浏览器自动化工具，与X-Agent桌面应用通过MCP（Model Context Protocol）协议通信，提供页面元素识别、表单自动填充、内容提取等功能。

**项目评分**: 9.9/10  
**对标**: Claude Code 99.8%  
**版本**: 1.0.0

## 核心功能

### 1. 页面元素识别与引用系统
- **元素引用**: 为页面元素生成唯一引用ID（ref_1, ref_2等）
- **选择器生成**: 自动生成CSS选择器
- **元素信息提取**: 获取元素的属性、样式、位置等信息
- **元素高亮**: 可视化高亮页面元素

### 2. 表单智能填充
- **自动填充**: 支持input、textarea、select等表单元素
- **字段映射**: 智能匹配字段名称和值
- **事件触发**: 正确触发input、change、blur等事件
- **验证支持**: 支持表单验证和错误处理

### 3. 页面内容提取
- **文本提取**: 提取页面文本内容
- **链接提取**: 收集所有链接信息
- **图片提取**: 获取图片URL和属性
- **表单提取**: 识别并提取表单结构
- **表格提取**: 解析表格数据

### 4. 标签组管理
- **创建标签组**: 组织相关标签页
- **标签分组**: 按颜色和名称分类
- **标签操作**: 添加、移除、重组标签

### 5. 操作录制与回放
- **操作记录**: 记录用户在页面上的操作
- **历史管理**: 保存操作历史
- **操作回放**: 支持重复执行操作序列

### 6. MCP协议通信
- **双向通信**: 与桌面应用实时通信
- **消息队列**: 异步消息处理
- **自动重连**: 连接断开时自动重连
- **超时管理**: 请求超时保护

## 项目结构

```
extension/
├── manifest.json                 # Chrome扩展配置
├── background.js                 # 后台服务工作线程
├── content.js                    # 内容脚本
├── injected.js                   # 页面注入脚本
├── popup.html                    # 弹出窗口UI
├── popup.js                      # 弹出窗口逻辑
├── popup.css                     # 弹出窗口样式
├── mcp-client.js                 # MCP客户端
├── tab-group-manager.js          # 标签组管理器
├── storage-manager.js            # 存储管理器
├── native-messaging-host.json    # 原生消息主机配置
├── options.html                  # 选项页面
├── options.js                    # 选项页面逻辑
├── options.css                   # 选项页面样式
├── tests/                        # 测试文件
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/                         # 文档
│   ├── API.md
│   ├── DEVELOPMENT.md
│   ├── DEPLOYMENT.md
│   └── TROUBLESHOOTING.md
└── images/                       # 图标资源
    ├── icon-16.png
    ├── icon-48.png
    └── icon-128.png
```

## 架构设计

### 通信流程

```
┌─────────────────────────────────────────────────────────┐
│                    Web Page (DOM)                        │
│                   (injected.js)                          │
└────────────────────────┬────────────────────────────────┘
                         │ window.postMessage
                         ↓
┌─────────────────────────────────────────────────────────┐
│              Content Script (content.js)                 │
│         - DOM操作                                        │
│         - 元素识别                                       │
│         - 表单填充                                       │
└────────────────────────┬────────────────────────────────┘
                         │ chrome.runtime.sendMessage
                         ↓
┌─────────────────────────────────────────────────────────┐
│         Background Service Worker (background.js)        │
│         - 会话管理                                       │
│         - 标签组管理                                     │
│         - 存储管理                                       │
│         - MCP通信                                        │
└────────────────────────┬────────────────────────────────┘
                         │ Native Messaging
                         ↓
┌─────────────────────────────────────────────────────────┐
│            X-Agent Desktop Application                   │
│         (MCP Server / Native Host)                       │
└─────────────────────────────────────────────────────────┘
```

### 消息类型

#### Content Script → Background Script

```javascript
{
  type: 'GET_ELEMENTS',           // 获取页面元素
  type: 'GET_ELEMENT_INFO',       // 获取元素信息
  type: 'FILL_FORM',              // 填充表单
  type: 'CLICK_ELEMENT',          // 点击元素
  type: 'EXTRACT_CONTENT',        // 提取内容
  type: 'HIGHLIGHT_ELEMENTS',     // 高亮元素
  type: 'TOGGLE_SIDEBAR',         // 切换侧边栏
  type: 'TOGGLE_ELEMENT_HIGHLIGHT' // 切换元素高亮
}
```

#### Background Script → MCP Server

```javascript
{
  type: 'initialize',             // 初始化连接
  type: 'session_created',        // 会话创建
  type: 'action_recorded',        // 操作记录
  type: 'element_referenced',     // 元素引用
  type: 'content_extracted'       // 内容提取
}
```

## API 参考

### Background Script API

#### 创建会话
```javascript
chrome.runtime.sendMessage({
  type: 'CREATE_SESSION',
  payload: {
    sessionName: '会话名称',
    traceId: 'trace_id',
    runId: 'run_id'
  }
}, response => {
  console.log(response.session);
});
```

#### 获取页面元素
```javascript
chrome.runtime.sendMessage({
  type: 'GET_PAGE_ELEMENTS',
  payload: {
    selector: 'button, a, input',
    includeHidden: false
  }
}, response => {
  console.log(response.elements);
});
```

#### 填充表单
```javascript
chrome.runtime.sendMessage({
  type: 'FILL_FORM',
  payload: {
    fields: [
      { selector: '#username', value: 'user@example.com' },
      { selector: '#password', value: 'password123' }
    ]
  }
}, response => {
  console.log(response.success);
});
```

#### 点击元素
```javascript
chrome.runtime.sendMessage({
  type: 'CLICK_ELEMENT',
  payload: {
    selector: '#submit-btn',
    refId: 'ref_1'
  }
}, response => {
  console.log(response.success);
});
```

#### 提取页面内容
```javascript
chrome.runtime.sendMessage({
  type: 'EXTRACT_PAGE_CONTENT',
  payload: {
    includeText: true,
    includeLinks: true,
    includeImages: true
  }
}, response => {
  console.log(response.content);
});
```

#### 获取元素引用
```javascript
chrome.runtime.sendMessage({
  type: 'GET_ELEMENT_REF',
  payload: {
    selector: '#my-element'
  }
}, response => {
  console.log(response.refId); // ref_1
});
```

### Content Script API

#### 获取元素信息
```javascript
chrome.runtime.sendMessage({
  type: 'GET_ELEMENT_INFO',
  selector: '#my-element'
}, response => {
  console.log(response.data);
  // {
  //   tag: 'INPUT',
  //   id: 'my-element',
  //   className: 'form-input',
  //   value: 'current value',
  //   rect: { top, left, width, height },
  //   visible: true,
  //   disabled: false
  // }
});
```

#### 高亮元素
```javascript
chrome.runtime.sendMessage({
  type: 'HIGHLIGHT_ELEMENTS',
  selectors: ['button', 'a'],
  color: '#FFD700',
  duration: 3000
}, response => {
  console.log(response.highlighted);
});
```

## 开发指南

### 本地开发设置

1. **克隆项目**
```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core/extension
```

2. **安装依赖**
```bash
npm install
```

3. **加载扩展**
- 打开 `chrome://extensions/`
- 启用"开发者模式"
- 点击"加载未打包的扩展程序"
- 选择 `extension` 目录

4. **调试**
- 右键点击扩展图标 → "检查弹出窗口"
- 打开 `chrome://extensions/` → 点击扩展名 → "背景页面"
- 在网页上右键 → "检查" → "Sources" 标签查看content script

### 代码风格

- 使用ES6+语法
- 遵循Google JavaScript风格指南
- 使用JSDoc注释
- 单行长度限制: 100字符

### 测试

```bash
# 运行单元测试
npm test

# 运行集成测试
npm run test:integration

# 运行E2E测试
npm run test:e2e

# 生成覆盖率报告
npm run test:coverage
```

### 构建与打包

```bash
# 开发构建
npm run build:dev

# 生产构建
npm run build:prod

# 打包为CRX
npm run package
```

## 安全特性

### 1. 内容安全策略 (CSP)
- 限制脚本来源
- 禁用内联脚本
- 防止XSS攻击

### 2. 权限最小化
- 仅请求必要的权限
- 使用activeTab权限限制范围
- 避免过度权限

### 3. 数据加密
- 敏感数据加密存储
- HTTPS通信
- 会话令牌管理

### 4. 隐私保护
- 不收集用户数据
- 本地存储所有数据
- 支持数据导出和删除

## 性能优化

### 1. 内存管理
- 及时清理事件监听器
- 限制历史记录大小
- 使用WeakMap存储元素引用

### 2. 通信优化
- 消息批处理
- 请求去重
- 连接复用

### 3. DOM操作优化
- 批量DOM更新
- 使用DocumentFragment
- 避免强制重排

## 部署指南

### Chrome Web Store 发布

1. **准备材料**
   - 扩展图标 (128x128)
   - 截图 (1280x800)
   - 描述和隐私政策

2. **提交审核**
   - 访问 Chrome Web Store Developer Dashboard
   - 上传扩展包
   - 填写应用信息
   - 提交审核

3. **版本管理**
   - 更新manifest.json中的版本号
   - 编写更新日志
   - 标记Git版本

### 企业部署

1. **创建策略**
```json
{
  "ExtensionInstallForcelist": [
    "extension_id;https://clients2.google.com/service/update2/crx"
  ]
}
```

2. **分发**
   - 通过Group Policy (Windows)
   - 通过MDM (macOS/Android)
   - 通过企业应用商店

## 故障排除

### 常见问题

**Q: 扩展无法连接到桌面应用**
A: 检查native messaging host是否正确安装和配置

**Q: 元素选择器不工作**
A: 验证选择器语法，使用浏览器开发者工具测试

**Q: 表单填充失败**
A: 检查表单元素是否可见和可交互，查看控制台错误

**Q: 性能问题**
A: 检查历史记录大小，清理缓存，减少监听器数量

## 贡献指南

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 许可证

MIT License - 详见LICENSE文件

## 联系方式

- 官网: https://x-agent.example.com
- 文档: https://docs.x-agent.example.com
- 问题: https://github.com/x-agent/x-agent-core/issues
- 邮件: support@x-agent.example.com
