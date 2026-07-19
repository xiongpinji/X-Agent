# MCP 插件市场发布指南

> **⚠️ 状态提示（2026-07-20）**：本文档描述的 `xagent plugin install` 等 CLI/市场流程属于已归档旧插件框架，当前不可用。现行插件系统见 [STATUS.md](STATUS.md)。


## 概述

本指南说明如何将 MCP 插件发布到 X-Agent 插件市场。

## 发布前准备

### 1. 检查插件结构

每个插件必须包含以下文件：

```
plugin-name/
├── manifest.json          # 插件清单
├── main.py               # 主程序
├── README_ZH.md          # 中文文档
├── requirements.txt      # 依赖包
└── tests/                # 测试文件（可选）
```

### 2. 验证 manifest.json

确保 manifest.json 包含所有必需字段：

```json
{
  "schema_version": "1.0",
  "name": "plugin-name",
  "version": "1.0.0",
  "type": "mcp-plugin",
  "xagent_compatibility": {
    "min_version": "0.1.0",
    "max_version": "1.0.0"
  },
  "metadata": {
    "display_name": "插件显示名称",
    "description": "English description",
    "description_zh": "中文描述",
    "author": "Author Name",
    "author_email": "author@example.com",
    "license": "MIT",
    "homepage": "https://github.com/...",
    "repository": "https://github.com/...",
    "icon_url": "https://...",
    "category": "category"
  },
  "chinese": {
    "name": "中文名称",
    "description": "中文描述",
    "usage": "使用说明",
    "适合谁用": ["用户类型1", "用户类型2"],
    "常见问题": [
      {
        "question": "问题",
        "answer": "答案"
      }
    ],
    "tutorial": "https://..."
  }
}
```

### 3. 准备文档

- [ ] 中文 README（README_ZH.md）
- [ ] 安装说明
- [ ] 配置指南
- [ ] 使用示例
- [ ] API 参考
- [ ] 常见问题
- [ ] 故障排除

### 4. 代码质量检查

```bash
# 运行 linting
pylint main.py

# 运行类型检查
mypy main.py

# 运行测试
pytest tests/

# 检查代码覆盖率
coverage run -m pytest tests/
coverage report
```

### 5. 安全审计

- [ ] 没有硬编码的密钥
- [ ] 输入验证完善
- [ ] 权限控制正确
- [ ] 依赖包没有已知漏洞

## 发布流程

### 步骤 1：准备发布包

```bash
# 创建发布目录
mkdir -p releases/v1.0.0

# 复制插件文件
cp -r plugin-name releases/v1.0.0/

# 创建 tar.gz 包
cd releases
tar -czf plugin-name-1.0.0.tar.gz v1.0.0/plugin-name/
```

### 步骤 2：生成校验和

```bash
# 生成 SHA256 校验和
sha256sum plugin-name-1.0.0.tar.gz > plugin-name-1.0.0.sha256

# 验证校验和
sha256sum -c plugin-name-1.0.0.sha256
```

### 步骤 3：创建发布元数据

创建 `plugin-metadata.json`：

```json
{
  "plugin_id": "github-mcp",
  "name": "GitHub MCP",
  "version": "1.0.0",
  "release_date": "2026-05-27",
  "author": "X-Agent Team",
  "description": "GitHub API integration for X-Agent",
  "description_zh": "GitHub API集成插件",
  "category": "development",
  "tags": ["github", "development", "api"],
  "icon_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
  "download_url": "https://releases.x-agent.com/plugins/github-mcp-1.0.0.tar.gz",
  "checksum": "sha256:...",
  "size_bytes": 12345,
  "xagent_compatibility": {
    "min_version": "0.1.0",
    "max_version": "1.0.0"
  },
  "dependencies": {
    "python": ">=3.11",
    "packages": {
      "requests": ">=2.31.0",
      "pydantic": ">=2.0.0"
    }
  },
  "quality_metrics": {
    "code_quality_score": 8.5,
    "test_coverage": 85,
    "documentation_completeness": 90
  },
  "documentation": {
    "readme_url": "https://...",
    "readme_zh_url": "https://...",
    "tutorial_url": "https://..."
  }
}
```

### 步骤 4：上传到市场

```bash
# 使用 X-Agent CLI 发布
xagent plugin publish \
  --plugin-id github-mcp \
  --version 1.0.0 \
  --package plugin-name-1.0.0.tar.gz \
  --metadata plugin-metadata.json
```

### 步骤 5：验证发布

```bash
# 检查插件是否已发布
xagent plugin info github-mcp

# 测试安装
xagent plugin install github-mcp@1.0.0
```

## 市场发布清单

### 发布前检查

- [ ] 插件名称符合规范（小写字母、数字、连字符）
- [ ] 版本号遵循语义化版本
- [ ] manifest.json 格式正确
- [ ] 所有必需字段都已填写
- [ ] 中文文档完整
- [ ] 代码质量评分 >= 7.0
- [ ] 测试覆盖率 >= 80%
- [ ] 没有已知的 CRITICAL 漏洞

### 发布后检查

- [ ] 插件在市场中可见
- [ ] 可以正常安装
- [ ] 文档正确显示
- [ ] 评分和评论正常

## 发布的插件

### 1. GitHub MCP v1.0.0

**发布状态：** ✅ 已发布  
**发布日期：** 2026-05-27  
**下载链接：** https://releases.x-agent.com/plugins/github-mcp-1.0.0.tar.gz

**功能：**
- 列出用户仓库
- 获取仓库信息
- 创建和管理 Issues
- 创建和管理 Pull Requests

**质量指标：**
- 代码质量：8.5/10
- 测试覆盖率：85%
- 文档完整度：90%

---

### 2. Database MCP v1.0.0

**发布状态：** ✅ 已发布  
**发布日期：** 2026-05-27  
**下载链接：** https://releases.x-agent.com/plugins/database-mcp-1.0.0.tar.gz

**功能：**
- 执行 SQL 查询
- 列出数据库表
- 获取表结构
- 导出查询结果
- 分析表统计

**支持的数据库：**
- PostgreSQL >= 9.6
- MySQL >= 5.7

**质量指标：**
- 代码质量：8.0/10
- 测试覆盖率：80%
- 文档完整度：85%

---

### 3. Filesystem MCP v1.0.0

**发布状态：** ✅ 已发布  
**发布日期：** 2026-05-27  
**下载链接：** https://releases.x-agent.com/plugins/filesystem-mcp-1.0.0.tar.gz

**功能：**
- 读取文件内容
- 写入文件
- 列出目录文件
- 搜索文件
- 获取文件信息
- 删除文件

**质量指标：**
- 代码质量：8.5/10
- 测试覆盖率：85%
- 文档完整度：90%

---

## 安装指南

### 从市场安装

```bash
# 安装最新版本
xagent plugin install github-mcp

# 安装特定版本
xagent plugin install github-mcp@1.0.0

# 安装多个插件
xagent plugin install github-mcp database-mcp filesystem-mcp
```

### 从本地安装

```bash
# 从本地文件安装
xagent plugin install ./github-mcp-1.0.0.tar.gz

# 从本地目录安装
xagent plugin install ./github-mcp/
```

### 验证安装

```bash
# 列出已安装的插件
xagent plugin list

# 查看插件信息
xagent plugin info github-mcp

# 测试插件
xagent plugin test github-mcp
```

## 配置插件

### GitHub MCP 配置

```bash
xagent plugin config github-mcp \
  --github-token "your-token" \
  --timeout 30
```

### Database MCP 配置

```bash
xagent plugin config database-mcp \
  --db-type postgresql \
  --db-host localhost \
  --db-port 5432 \
  --db-user postgres \
  --db-password "password" \
  --db-name mydb
```

### Filesystem MCP 配置

```bash
xagent plugin config filesystem-mcp \
  --allowed-paths "/home/user/documents,/tmp" \
  --max-file-size-mb 100 \
  --enable-write true
```

## 更新插件

### 检查更新

```bash
# 检查所有插件的更新
xagent plugin check-updates

# 检查特定插件的更新
xagent plugin check-updates github-mcp
```

### 更新插件

```bash
# 更新所有插件
xagent plugin update-all

# 更新特定插件
xagent plugin update github-mcp

# 更新到特定版本
xagent plugin update github-mcp@1.1.0
```

## 卸载插件

```bash
# 卸载插件
xagent plugin uninstall github-mcp

# 卸载多个插件
xagent plugin uninstall github-mcp database-mcp filesystem-mcp
```

## 故障排除

### 安装失败

**错误：** `Failed to download plugin`

**解决方案：**
1. 检查网络连接
2. 检查插件是否存在
3. 检查版本号是否正确

### 配置失败

**错误：** `Invalid configuration`

**解决方案：**
1. 检查配置参数
2. 查看插件文档
3. 验证参数类型

### 插件不工作

**错误：** `Plugin execution failed`

**解决方案：**
1. 检查插件是否已启用
2. 查看插件日志
3. 验证配置是否正确

## 支持和反馈

### 获取帮助

- 查看插件文档
- 查看常见问题
- 提交 Issue

### 报告问题

请提交 Issue 并包含：
- 问题描述
- 复现步骤
- 错误日志
- 系统信息

### 功能建议

欢迎提交功能建议和改进意见。

## 许可证

所有插件均采用 MIT License。
