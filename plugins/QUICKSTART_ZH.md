# MCP 插件快速开始指南

## 概述

本指南帮助你快速安装和使用 X-Agent 的三个核心 MCP 插件：
- GitHub MCP 插件
- 数据库 MCP 插件
- 文件系统 MCP 插件

## 系统要求

- **操作系统：** Linux、macOS 或 Windows
- **Python 版本：** >= 3.11
- **X-Agent 版本：** >= 0.1.0
- **网络连接：** 需要互联网连接（用于 GitHub 插件）

## 安装步骤

### 1. 安装 X-Agent

```bash
# 使用 pip 安装
pip install x-agent

# 或从源代码安装
git clone https://github.com/x-agent/x-agent.git
cd x-agent
pip install -e .
```

### 2. 安装 MCP 插件

#### 方法 A：从市场安装（推荐）

```bash
# 安装所有三个插件
xagent plugin install github-mcp database-mcp filesystem-mcp

# 或逐个安装
xagent plugin install github-mcp
xagent plugin install database-mcp
xagent plugin install filesystem-mcp
```

#### 方法 B：从本地安装

```bash
# 复制插件到 X-Agent plugins 目录
cp -r github-mcp /path/to/xagent/plugins/
cp -r database-mcp /path/to/xagent/plugins/
cp -r filesystem-mcp /path/to/xagent/plugins/

# 重启 X-Agent
xagent restart
```

### 3. 验证安装

```bash
# 列出已安装的插件
xagent plugin list

# 应该看到：
# - github-mcp (v1.0.0)
# - database-mcp (v1.0.0)
# - filesystem-mcp (v1.0.0)
```

## 配置插件

### GitHub MCP 配置

#### 获取 GitHub Token

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token"
3. 选择 "repo" 权限
4. 生成并复制 Token

#### 配置插件

```bash
xagent plugin config github-mcp \
  --github-token "ghp_xxxxxxxxxxxxxxxxxxxx" \
  --timeout 30
```

或编辑配置文件 `~/.xagent/plugins/github-mcp.json`：

```json
{
  "github_token": "ghp_xxxxxxxxxxxxxxxxxxxx",
  "timeout": 30
}
```

### 数据库 MCP 配置

#### PostgreSQL 配置

```bash
xagent plugin config database-mcp \
  --db-type postgresql \
  --db-host localhost \
  --db-port 5432 \
  --db-user postgres \
  --db-password "your-password" \
  --db-name mydb \
  --timeout 30
```

#### MySQL 配置

```bash
xagent plugin config database-mcp \
  --db-type mysql \
  --db-host localhost \
  --db-port 3306 \
  --db-user root \
  --db-password "your-password" \
  --db-name mydb \
  --timeout 30
```

### 文件系统 MCP 配置

```bash
xagent plugin config filesystem-mcp \
  --allowed-paths "/home/user/documents,/tmp" \
  --max-file-size-mb 100 \
  --enable-write true
```

## 使用示例

### GitHub MCP 使用示例

#### 示例 1：列出仓库

```
用户: 列出我的前 5 个仓库
X-Agent: 使用 GitHub MCP 的 list_repositories 工具
```

**结果：**
```
找到 5 个仓库：
1. awesome-project (42 stars)
2. my-library (15 stars)
3. learning-python (8 stars)
4. web-app (5 stars)
5. cli-tool (3 stars)
```

#### 示例 2：创建 Issue

```
用户: 在 my-repo 中创建一个 Bug 报告
标题: 登录页面崩溃
描述: 在 Chrome 中访问登录页面时应用崩溃

X-Agent: 使用 GitHub MCP 的 create_issue 工具
```

**结果：**
```
Issue 已创建：
- Issue #123: 登录页面崩溃
- URL: https://github.com/user/my-repo/issues/123
- 状态: open
```

#### 示例 3：创建 Pull Request

```
用户: 创建一个从 feature/new-ui 到 main 的拉取请求
标题: 新的用户界面
描述: 实现了新的用户界面设计

X-Agent: 使用 GitHub MCP 的 create_pull_request 工具
```

**结果：**
```
Pull Request 已创建：
- PR #456: 新的用户界面
- URL: https://github.com/user/my-repo/pull/456
- 状态: open
```

### 数据库 MCP 使用示例

#### 示例 1：查询数据

```
用户: 查询用户表中的前 10 条记录

X-Agent: 使用 Database MCP 的 execute_query 工具
查询: SELECT * FROM users LIMIT 10
```

**结果：**
```
查询成功，返回 10 条记录：
ID | 名称 | 邮箱 | 创建时间
1  | 张三 | zhangsan@example.com | 2026-01-01
2  | 李四 | lisi@example.com | 2026-01-02
...
```

#### 示例 2：列出表

```
用户: 列出数据库中的所有表

X-Agent: 使用 Database MCP 的 list_tables 工具
```

**结果：**
```
数据库中有 3 个表：
1. users (1000 行)
2. orders (5000 行)
3. products (500 行)
```

#### 示例 3：导出数据

```
用户: 将用户数据导出为 CSV 文件

X-Agent: 使用 Database MCP 的 export_query_result 工具
查询: SELECT id, name, email FROM users
格式: csv
文件名: users_export.csv
```

**结果：**
```
数据已导出：
- 文件: users_export.csv
- 行数: 1000
- 大小: 45KB
```

### 文件系统 MCP 使用示例

#### 示例 1：读取文件

```
用户: 读取 /home/user/documents/readme.txt 文件

X-Agent: 使用 Filesystem MCP 的 read_file 工具
```

**结果：**
```
文件内容：
这是一个示例文件...
[文件内容显示]
```

#### 示例 2：搜索文件

```
用户: 搜索所有 Python 文件

X-Agent: 使用 Filesystem MCP 的 search_files 工具
目录: /home/user/projects
模式: *.py
```

**结果：**
```
找到 5 个 Python 文件：
1. /home/user/projects/main.py
2. /home/user/projects/utils/helper.py
3. /home/user/projects/tests/test_main.py
...
```

#### 示例 3：写入文件

```
用户: 创建一个新的配置文件

X-Agent: 使用 Filesystem MCP 的 write_file 工具
路径: /home/user/documents/config.txt
内容: [配置内容]
```

**结果：**
```
文件已创建：
- 路径: /home/user/documents/config.txt
- 大小: 256 字节
```

## 常见任务

### 任务 1：管理 GitHub 仓库

```
1. 列出所有仓库
   用户: 列出我的仓库
   
2. 查看仓库详情
   用户: 获取 my-repo 的详细信息
   
3. 查看 Issues
   用户: 列出 my-repo 中的所有开放问题
   
4. 创建 Issue
   用户: 创建一个新的 Issue
   
5. 创建 Pull Request
   用户: 创建一个新的 Pull Request
```

### 任务 2：查询数据库

```
1. 连接数据库
   配置数据库连接信息
   
2. 查询数据
   用户: 查询用户表
   
3. 分析数据
   用户: 统计订单总额
   
4. 导出数据
   用户: 导出查询结果为 CSV
   
5. 管理表
   用户: 列出所有表
```

### 任务 3：管理文件

```
1. 读取文件
   用户: 读取配置文件
   
2. 搜索文件
   用户: 搜索所有日志文件
   
3. 写入文件
   用户: 创建新文件
   
4. 获取文件信息
   用户: 获取文件大小
   
5. 删除文件
   用户: 删除旧文件
```

## 故障排除

### 问题 1：插件安装失败

**错误信息：** `Failed to install plugin`

**解决方案：**
```bash
# 检查网络连接
ping github.com

# 检查 Python 版本
python --version

# 尝试重新安装
xagent plugin install github-mcp --force
```

### 问题 2：配置失败

**错误信息：** `Invalid configuration`

**解决方案：**
```bash
# 检查配置文件
cat ~/.xagent/plugins/github-mcp.json

# 重新配置
xagent plugin config github-mcp --reset
xagent plugin config github-mcp --github-token "your-token"
```

### 问题 3：插件不工作

**错误信息：** `Plugin execution failed`

**解决方案：**
```bash
# 检查插件状态
xagent plugin status github-mcp

# 查看插件日志
xagent plugin logs github-mcp

# 重启插件
xagent plugin restart github-mcp
```

### 问题 4：GitHub Token 无效

**错误信息：** `401 Unauthorized`

**解决方案：**
1. 检查 Token 是否过期
2. 重新生成 Token
3. 更新配置

```bash
xagent plugin config github-mcp --github-token "new-token"
```

### 问题 5：数据库连接失败

**错误信息：** `Connection refused`

**解决方案：**
1. 检查数据库服务是否运行
2. 检查主机和端口
3. 检查用户名和密码

```bash
# 测试连接
xagent plugin test database-mcp
```

## 性能优化

### GitHub MCP 优化

- 使用 Token 认证以获得更高的 API 限制
- 缓存仓库信息以减少 API 调用
- 使用分页获取大量数据

### 数据库 MCP 优化

- 添加索引以加快查询
- 使用 LIMIT 限制返回行数
- 使用连接池管理数据库连接

### 文件系统 MCP 优化

- 避免递归搜索大目录
- 使用具体的文件名模式
- 限制文件大小

## 安全建议

### GitHub MCP 安全

- 使用强密码保护 Token
- 定期轮换 Token
- 不要在公开代码中暴露 Token
- 使用环境变量存储 Token

### 数据库 MCP 安全

- 使用强密码
- 限制数据库访问 IP
- 启用 SSL/TLS 加密
- 定期备份数据库

### 文件系统 MCP 安全

- 限制允许访问的目录
- 禁用不需要的写入操作
- 定期审计文件访问
- 备份重要文件

## 获取帮助

### 文档

- [GitHub MCP 文档](./github-mcp/README_ZH.md)
- [数据库 MCP 文档](./database-mcp/README_ZH.md)
- [文件系统 MCP 文档](./filesystem-mcp/README_ZH.md)

### 支持

- 提交 Issue：https://github.com/x-agent/x-agent/issues
- 查看常见问题：各插件文档中的 FAQ 部分
- 联系支持团队：support@x-agent.com

## 下一步

1. **配置插件** - 根据你的需求配置插件
2. **尝试示例** - 运行提供的示例
3. **集成到工作流** - 将插件集成到你的工作流中
4. **提供反馈** - 分享你的使用体验

## 许可证

所有插件均采用 MIT License。

## 更新日志

### v1.0.0 (2026-05-27)
- 初始版本发布
- 支持 GitHub、数据库和文件系统操作
- 完整的中文文档
