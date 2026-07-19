# MCP 插件安装指南

> **⚠️ 状态提示（2026-07-20）**：本文档描述的 `xagent plugin install` 等 CLI/市场流程属于已归档旧插件框架，当前不可用。现行插件系统见 [STATUS.md](STATUS.md)。


## 目录

1. [系统要求](#系统要求)
2. [安装步骤](#安装步骤)
3. [配置指南](#配置指南)
4. [验证安装](#验证安装)
5. [故障排除](#故障排除)

---

## 系统要求

### 最低要求

- **操作系统：** Linux、macOS 或 Windows
- **Python 版本：** 3.11 或更高
- **X-Agent 版本：** 0.1.0 或更高
- **磁盘空间：** 至少 500MB
- **内存：** 至少 2GB

### 推荐配置

- **操作系统：** Ubuntu 20.04 LTS 或更高
- **Python 版本：** 3.11 或 3.12
- **X-Agent 版本：** 最新版本
- **磁盘空间：** 至少 1GB
- **内存：** 至少 4GB

### 网络要求

- 互联网连接（用于下载插件和依赖）
- GitHub API 访问（用于 GitHub 插件）
- 数据库网络访问（用于数据库插件）

---

## 安装步骤

### 步骤 1：安装 X-Agent

#### 使用 pip 安装

```bash
# 安装最新版本
pip install x-agent

# 或安装特定版本
pip install x-agent==0.1.0
```

#### 从源代码安装

```bash
# 克隆仓库
git clone https://github.com/x-agent/x-agent.git
cd x-agent

# 安装依赖
pip install -r requirements.txt

# 安装 X-Agent
pip install -e .
```

#### 验证安装

```bash
# 检查 X-Agent 版本
xagent --version

# 应该输出类似：
# X-Agent version 0.1.0
```

### 步骤 2：安装 MCP 插件

#### 方法 A：从市场安装（推荐）

```bash
# 安装所有三个插件
xagent plugin install github-mcp database-mcp filesystem-mcp

# 或逐个安装
xagent plugin install github-mcp
xagent plugin install database-mcp
xagent plugin install filesystem-mcp
```

#### 方法 B：从本地文件安装

```bash
# 下载插件包
wget https://releases.x-agent.com/plugins/github-mcp-1.0.0.tar.gz
wget https://releases.x-agent.com/plugins/database-mcp-1.0.0.tar.gz
wget https://releases.x-agent.com/plugins/filesystem-mcp-1.0.0.tar.gz

# 安装插件
xagent plugin install ./github-mcp-1.0.0.tar.gz
xagent plugin install ./database-mcp-1.0.0.tar.gz
xagent plugin install ./filesystem-mcp-1.0.0.tar.gz
```

#### 方法 C：从本地目录安装

```bash
# 复制插件到 X-Agent plugins 目录
XAGENT_HOME=$(xagent config get home)
cp -r github-mcp $XAGENT_HOME/plugins/
cp -r database-mcp $XAGENT_HOME/plugins/
cp -r filesystem-mcp $XAGENT_HOME/plugins/

# 重启 X-Agent
xagent restart
```

### 步骤 3：验证安装

```bash
# 列出已安装的插件
xagent plugin list

# 应该看到：
# Installed plugins:
# - github-mcp (v1.0.0)
# - database-mcp (v1.0.0)
# - filesystem-mcp (v1.0.0)
```

---

## 配置指南

### GitHub MCP 配置

#### 获取 GitHub Token

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token"
3. 输入 Token 名称（例如：X-Agent）
4. 选择以下权限：
   - `repo` - 完整的仓库访问权限
   - `read:user` - 读取用户信息
5. 点击 "Generate token"
6. 复制生成的 Token

#### 配置插件

**方法 1：使用命令行**

```bash
xagent plugin config github-mcp \
  --github-token "ghp_xxxxxxxxxxxxxxxxxxxx" \
  --timeout 30
```

**方法 2：编辑配置文件**

```bash
# 编辑配置文件
nano ~/.xagent/plugins/github-mcp.json
```

```json
{
  "github_token": "ghp_xxxxxxxxxxxxxxxxxxxx",
  "timeout": 30
}
```

**方法 3：使用环境变量**

```bash
export XAGENT_GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
export XAGENT_GITHUB_TIMEOUT=30
```

### 数据库 MCP 配置

#### PostgreSQL 配置

**方法 1：使用命令行**

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

**方法 2：编辑配置文件**

```bash
nano ~/.xagent/plugins/database-mcp.json
```

```json
{
  "db_type": "postgresql",
  "db_host": "localhost",
  "db_port": 5432,
  "db_user": "postgres",
  "db_password": "your-password",
  "db_name": "mydb",
  "timeout": 30
}
```

#### MySQL 配置

**方法 1：使用命令行**

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

**方法 2：编辑配置文件**

```bash
nano ~/.xagent/plugins/database-mcp.json
```

```json
{
  "db_type": "mysql",
  "db_host": "localhost",
  "db_port": 3306,
  "db_user": "root",
  "db_password": "your-password",
  "db_name": "mydb",
  "timeout": 30
}
```

### 文件系统 MCP 配置

**方法 1：使用命令行**

```bash
xagent plugin config filesystem-mcp \
  --allowed-paths "/home/user/documents,/tmp" \
  --max-file-size-mb 100 \
  --enable-write true
```

**方法 2：编辑配置文件**

```bash
nano ~/.xagent/plugins/filesystem-mcp.json
```

```json
{
  "allowed_paths": [
    "/home/user/documents",
    "/tmp"
  ],
  "max_file_size_mb": 100,
  "enable_write": true
}
```

---

## 验证安装

### 检查插件状态

```bash
# 查看所有插件的状态
xagent plugin status

# 查看特定插件的状态
xagent plugin status github-mcp
```

### 测试插件功能

```bash
# 测试 GitHub MCP
xagent plugin test github-mcp

# 测试数据库 MCP
xagent plugin test database-mcp

# 测试文件系统 MCP
xagent plugin test filesystem-mcp
```

### 查看插件日志

```bash
# 查看所有插件的日志
xagent plugin logs

# 查看特定插件的日志
xagent plugin logs github-mcp

# 实时查看日志
xagent plugin logs github-mcp --follow
```

### 验证配置

```bash
# 查看插件配置
xagent plugin config github-mcp --show

# 验证配置是否正确
xagent plugin config github-mcp --validate
```

---

## 故障排除

### 问题 1：安装失败

**错误信息：** `Failed to install plugin`

**可能原因：**
- 网络连接问题
- 插件不存在
- 版本不兼容

**解决方案：**

```bash
# 检查网络连接
ping github.com

# 检查 X-Agent 版本
xagent --version

# 尝试重新安装
xagent plugin install github-mcp --force

# 查看详细错误信息
xagent plugin install github-mcp --verbose
```

### 问题 2：配置失败

**错误信息：** `Invalid configuration`

**可能原因：**
- 配置参数错误
- 参数类型不匹配
- 必需参数缺失

**解决方案：**

```bash
# 查看配置文件
cat ~/.xagent/plugins/github-mcp.json

# 重置配置
xagent plugin config github-mcp --reset

# 重新配置
xagent plugin config github-mcp --github-token "your-token"

# 验证配置
xagent plugin config github-mcp --validate
```

### 问题 3：插件不工作

**错误信息：** `Plugin execution failed`

**可能原因：**
- 插件未启用
- 配置不正确
- 依赖包缺失

**解决方案：**

```bash
# 检查插件是否启用
xagent plugin status github-mcp

# 启用插件
xagent plugin enable github-mcp

# 查看插件日志
xagent plugin logs github-mcp

# 重启插件
xagent plugin restart github-mcp
```

### 问题 4：GitHub Token 无效

**错误信息：** `401 Unauthorized`

**可能原因：**
- Token 过期
- Token 权限不足
- Token 被撤销

**解决方案：**

```bash
# 生成新的 Token
# 访问 https://github.com/settings/tokens

# 更新配置
xagent plugin config github-mcp --github-token "new-token"

# 测试连接
xagent plugin test github-mcp
```

### 问题 5：数据库连接失败

**错误信息：** `Connection refused`

**可能原因：**
- 数据库服务未运行
- 主机或端口错误
- 用户名或密码错误

**解决方案：**

```bash
# 检查数据库服务状态
systemctl status postgresql  # 或 mysql

# 启动数据库服务
systemctl start postgresql   # 或 mysql

# 测试数据库连接
psql -h localhost -U postgres -d mydb  # PostgreSQL
mysql -h localhost -u root -p mydb     # MySQL

# 更新配置
xagent plugin config database-mcp \
  --db-host localhost \
  --db-user postgres \
  --db-password "password"

# 测试插件
xagent plugin test database-mcp
```

### 问题 6：文件权限错误

**错误信息：** `Permission denied`

**可能原因：**
- 文件权限不足
- 目录不在允许列表中
- 写入操作被禁用

**解决方案：**

```bash
# 检查文件权限
ls -la /home/user/documents

# 修改文件权限
chmod 644 /home/user/documents/file.txt

# 更新允许的目录
xagent plugin config filesystem-mcp \
  --allowed-paths "/home/user/documents,/tmp"

# 启用写入操作
xagent plugin config filesystem-mcp --enable-write true
```

---

## 卸载插件

### 卸载单个插件

```bash
xagent plugin uninstall github-mcp
```

### 卸载所有插件

```bash
xagent plugin uninstall github-mcp database-mcp filesystem-mcp
```

### 清理配置文件

```bash
# 删除插件配置
rm ~/.xagent/plugins/github-mcp.json
rm ~/.xagent/plugins/database-mcp.json
rm ~/.xagent/plugins/filesystem-mcp.json
```

---

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

---

## 性能优化

### 缓存配置

```bash
# 启用缓存
xagent plugin config github-mcp --enable-cache true

# 设置缓存过期时间（秒）
xagent plugin config github-mcp --cache-ttl 3600
```

### 连接池配置

```bash
# 设置数据库连接池大小
xagent plugin config database-mcp --pool-size 10

# 设置连接超时时间
xagent plugin config database-mcp --timeout 30
```

### 日志级别

```bash
# 设置日志级别
xagent plugin config github-mcp --log-level INFO

# 可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL
```

---

## 安全建议

### GitHub MCP 安全

- 使用强密码保护 Token
- 定期轮换 Token（建议每 90 天）
- 不要在公开代码中暴露 Token
- 使用环境变量或密钥管理系统存储 Token
- 定期审计 Token 的使用情况

### 数据库 MCP 安全

- 使用强密码
- 限制数据库访问 IP
- 启用 SSL/TLS 加密连接
- 定期备份数据库
- 使用最小权限原则创建数据库用户

### 文件系统 MCP 安全

- 限制允许访问的目录
- 禁用不需要的写入操作
- 定期审计文件访问
- 备份重要文件
- 使用文件权限限制访问

---

## 获取帮助

### 文档

- [快速开始指南](./QUICKSTART_ZH.md)
- [GitHub MCP 文档](./github-mcp/README_ZH.md)
- [数据库 MCP 文档](./database-mcp/README_ZH.md)
- [文件系统 MCP 文档](./filesystem-mcp/README_ZH.md)

### 支持

- 提交 Issue：https://github.com/x-agent/x-agent/issues
- 查看常见问题：各插件文档中的 FAQ 部分
- 联系支持团队：support@x-agent.com

---

## 许可证

所有插件均采用 MIT License。
