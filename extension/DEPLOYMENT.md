# X-Agent Chrome Extension 部署指南

## 目录

1. [开发环境部署](#开发环境部署)
2. [生产环境部署](#生产环境部署)
3. [Chrome Web Store发布](#chrome-web-store发布)
4. [企业部署](#企业部署)
5. [更新和维护](#更新和维护)

## 开发环境部署

### 前置要求

- Node.js 16+ 和 npm 8+
- Chrome 90+ 浏览器
- Git版本控制
- 文本编辑器（VS Code推荐）

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core/extension
```

2. **安装依赖**
```bash
npm install
```

3. **构建开发版本**
```bash
npm run build:dev
```

4. **加载到Chrome**
- 打开 `chrome://extensions/`
- 启用右上角的"开发者模式"
- 点击"加载未打包的扩展程序"
- 选择项目的 `extension` 目录

5. **验证安装**
- 扩展图标应该出现在Chrome工具栏
- 右键点击图标，选择"选项"验证配置

### 开发工作流

```bash
# 启动监视模式（自动重新构建）
npm run watch

# 在另一个终端运行测试
npm test -- --watch

# 代码检查
npm run lint

# 代码格式化
npm run format
```

### 调试技巧

#### 启用调试模式
```javascript
// 在popup.js或background.js中
const DEBUG = true;

if (DEBUG) {
  console.log('[X-Agent Debug]', message);
}
```

#### 查看后台脚本日志
1. 打开 `chrome://extensions/`
2. 找到X-Agent扩展
3. 点击"背景页面"链接
4. 在打开的开发者工具中查看日志

#### 查看Content Script日志
1. 在任何网页上右键 → "检查"
2. 打开"控制台"标签
3. 查看 `[X-Agent]` 前缀的消息

## 生产环境部署

### 构建生产版本

```bash
# 生产构建（压缩和优化）
npm run build:prod

# 验证构建输出
ls -la dist/
```

### 性能优化

1. **代码压缩**
```bash
# 使用webpack生产模式自动压缩
npm run build:prod
```

2. **资源优化**
- 压缩图片资源
- 移除调试代码
- 最小化CSS和JavaScript

3. **性能测试**
```bash
# 运行性能基准测试
npm run test:performance
```

### 安全检查

1. **权限审计**
```bash
# 检查manifest.json中的权限
cat manifest.json | grep -A 20 '"permissions"'
```

2. **依赖检查**
```bash
# 检查已知漏洞
npm audit

# 修复漏洞
npm audit fix
```

3. **代码审查**
```bash
# 运行安全检查
npm run lint
npm run test
```

## Chrome Web Store发布

### 准备材料

#### 1. 扩展图标
- 128x128 像素 PNG格式
- 清晰可识别的设计
- 支持透明背景

#### 2. 截图
- 1280x800 像素
- 最多5张
- 展示主要功能

#### 3. 描述文案
```
简短描述（132字符以内）：
X-Agent Chrome扩展 - 智能浏览器自动化工具

详细描述：
X-Agent是一个强大的浏览器自动化工具，提供：
- 页面元素识别和引用
- 表单智能填充
- 内容提取和分析
- 操作录制和回放
- 与X-Agent桌面应用集成

功能特性：
✓ 自动识别页面元素
✓ 智能表单填充
✓ 内容提取
✓ 操作录制
✓ 标签组管理
✓ MCP协议通信
```

#### 4. 隐私政策
```
X-Agent Chrome扩展隐私政策

数据收集：
- 本扩展不收集任何用户数据
- 所有数据存储在本地
- 不与第三方共享数据

权限使用：
- activeTab: 仅用于当前标签页操作
- storage: 本地存储会话和设置
- scripting: 页面自动化操作

联系方式：
privacy@x-agent.example.com
```

### 发布流程

1. **创建开发者账户**
   - 访问 [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
   - 使用Google账户登录
   - 支付一次性注册费（$5）

2. **打包扩展**
```bash
npm run package
# 生成 x-agent-extension.zip
```

3. **上传到Web Store**
   - 打开Developer Dashboard
   - 点击"新建项目"
   - 上传 `x-agent-extension.zip`
   - 填写应用信息

4. **填写应用详情**
   - 应用名称
   - 简短描述
   - 详细描述
   - 类别：生产力工具
   - 语言：中文、英文
   - 上传图标和截图

5. **隐私和权限**
   - 上传隐私政策
   - 声明权限用途
   - 确认不收集用户数据

6. **提交审核**
   - 检查所有信息
   - 点击"提交审核"
   - 等待Google审核（通常3-7天）

7. **发布**
   - 审核通过后自动发布
   - 在Chrome Web Store中可见
   - 用户可以安装

### 版本管理

```bash
# 更新版本号
# 编辑 manifest.json
{
  "version": "1.0.1"
}

# 编辑 package.json
{
  "version": "1.0.1"
}

# 创建Git标签
git tag v1.0.1
git push origin v1.0.1

# 构建和发布
npm run build:prod
npm run package
# 上传到Web Store
```

## 企业部署

### 通过Group Policy部署（Windows）

1. **创建策略文件**
```json
{
  "ExtensionInstallForcelist": [
    "extension_id;https://clients2.google.com/service/update2/crx"
  ],
  "ExtensionInstallBlocklist": ["*"],
  "ExtensionSettings": {
    "extension_id": {
      "installation_mode": "force_installed",
      "update_url": "https://clients2.google.com/service/update2/crx"
    }
  }
}
```

2. **部署策略**
   - 使用Group Policy Editor (gpedit.msc)
   - 导航到 Computer Configuration > Administrative Templates > Google > Google Chrome > Extensions
   - 导入策略文件

### 通过MDM部署（macOS/iOS）

1. **配置MDM服务器**
   - 上传扩展到MDM服务器
   - 配置分发策略

2. **用户设备**
   - 设备自动接收扩展
   - 用户无法卸载

### 自托管部署

1. **设置更新服务器**
```xml
<?xml version='1.0' encoding='UTF-8'?>
<gupdate xmlns='http://www.google.com/update2/response' protocol='3.0'>
  <app appid='extension_id'>
    <updatecheck codebase='https://your-server.com/extension.crx' version='1.0.0' />
  </app>
</gupdate>
```

2. **配置Chrome策略**
```json
{
  "ExtensionInstallSources": [
    "https://your-server.com/*"
  ]
}
```

## 更新和维护

### 定期更新

```bash
# 检查依赖更新
npm outdated

# 更新依赖
npm update

# 检查安全漏洞
npm audit
npm audit fix
```

### 版本发布流程

1. **开发新功能**
```bash
git checkout -b feature/new-feature
# 开发和测试
git commit -m "feat: add new feature"
```

2. **准备发布**
```bash
# 更新版本号
npm version minor  # 或 major, patch

# 更新CHANGELOG
echo "## v1.0.1\n- New feature\n- Bug fixes" >> CHANGELOG.md

# 提交更改
git add .
git commit -m "chore: release v1.0.1"
git tag v1.0.1
git push origin main --tags
```

3. **构建和发布**
```bash
npm run build:prod
npm run package
# 上传到Web Store
```

### 监控和日志

1. **启用错误报告**
```javascript
// 在background.js中
window.addEventListener('error', (event) => {
  console.error('[X-Agent Error]', event.error);
  // 发送到错误追踪服务
});
```

2. **性能监控**
```javascript
// 测量操作性能
const start = performance.now();
// 执行操作
const duration = performance.now() - start;
console.log(`操作耗时: ${duration}ms`);
```

### 用户反馈

1. **收集反馈**
   - Chrome Web Store评论
   - GitHub Issues
   - 用户邮件

2. **处理问题**
   - 优先级排序
   - 分配给开发者
   - 跟踪进度

3. **发布修复**
   - 快速修复关键问题
   - 定期发布更新

## 故障排除

### 部署问题

**问题：上传到Web Store失败**
- 检查zip文件格式
- 验证manifest.json有效性
- 确保所有文件都包含在内

**问题：审核被拒绝**
- 检查隐私政策
- 验证权限声明
- 确保功能描述准确

**问题：用户无法安装**
- 检查浏览器版本
- 验证扩展ID
- 查看安装错误日志

### 性能问题

**问题：扩展加载缓慢**
- 优化初始化代码
- 减少依赖大小
- 使用代码分割

**问题：内存占用过高**
- 清理事件监听器
- 限制缓存大小
- 使用WeakMap

## 最佳实践

1. **定期备份**
   - 备份源代码
   - 备份用户数据
   - 备份配置文件

2. **安全更新**
   - 及时修复漏洞
   - 测试所有更新
   - 逐步推出更新

3. **用户沟通**
   - 发布更新说明
   - 收集用户反馈
   - 及时回应问题

4. **监控指标**
   - 安装数量
   - 活跃用户
   - 错误率
   - 性能指标
