# MCP 配置指南

本指南介绍如何配置和管理 X-Agent 中的 MCP（Model Context Protocol）服务器和工具。

## 目录

- [快速开始](#快速开始)
- [配置文件格式](#配置文件格式)
- [服务器配置](#服务器配置)
- [全局配置](#全局配置)
- [安全配置](#安全配置)
- [性能配置](#性能配置)
- [监控配置](#监控配置)
- [常见配置场景](#常见配置场景)
- [最佳实践](#最佳实践)

---

## 快速开始

### 1. 复制配置文件

```bash
cp config/mcp_servers.example.yaml config/mcp_servers.yaml
```

### 2. 编辑配置文件

根据你的需求修改 `config/mcp_servers.yaml`：

```yaml
mcp_servers:
  - name: "filesystem"
    url: "http://localhost:8001"
    enabled: true
    auto_register: true
```

### 3. 启动应用

应用启动时会自动加载并初始化 MCP 服务器。

---

## 配置文件格式

MCP 配置文件采用 YAML 格式，位置为 `config/mcp_servers.yaml`。

### 文件结构

```yaml
# MCP 服务器列表
mcp_servers:
  - name: "server_name"
    url: "http://host:port"
    # ... 服务器配置

# 全局配置
global:
  # ... 全局设置

# 工具过滤规则
filters:
  # ... 过滤规则

# 安全配置
security:
  # ... 安全设置

# 性能配置
performance:
  # ... 性能设置

# 监控配置
monitoring:
  # ... 监控设置
```

---

## 服务器配置

### 基本参数

每个 MCP 服务器配置包含以下参数：

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 服务器唯一标识符 |
| `url` | string | 是 | - | 服务器 URL（如 `http://localhost:8001`） |
| `enabled` | boolean | 否 | `true` | 是否启用此服务器 |
| `auto_register` | boolean | 否 | `true` | 是否自动发现并注册工具 |
| `timeout` | float | 否 | `30.0` | 请求超时时间（秒） |
| `max_retries` | integer | 否 | `3` | 最大重试次数 |
| `tags` | array | 否 | `[]` | 服务器标签 |
| `description` | string | 否 | - | 服务器描述 |

### 配置示例

#### 文件系统服务器

```yaml
- name: "filesystem"
  url: "http://localhost:8001"
  enabled: true
  auto_register: true
  timeout: 30.0
  max_retries: 3
  tags:
    - "filesystem"
    - "local"
  description: "本地文件系统操作工具"
```

#### 数据库服务器

```yaml
- name: "database"
  url: "http://localhost:8002"
  enabled: true
  auto_register: true
  timeout: 30.0
  max_retries: 3
  tags:
    - "database"
    - "sql"
  description: "数据库查询和操作工具"
```

#### 浏览器自动化服务器

```yaml
- name: "browser"
  url: "http://localhost:8005"
  enabled: true
  auto_register: true
  timeout: 60.0  # 浏览器操作可能需要更长时间
  max_retries: 2
  tags:
    - "browser"
    - "automation"
  description: "浏览器自动化和网页交互工具"
```

#### 禁用的服务器

```yaml
- name: "git"
  url: "http://localhost:8004"
  enabled: false  # 默认禁用
  auto_register: true
  tags:
    - "git"
    - "vcs"
  description: "Git 版本控制操作工具"
```

---

## 全局配置

全局配置影响所有 MCP 服务器的行为。

### 参数说明

```yaml
global:
  # 是否在启动时自动发现所有工具
  auto_discover_on_startup: true

  # 工具发现失败时的行为
  # "ignore" - 忽略错误继续启动
  # "warn" - 记录警告但继续启动
  # "fail" - 启动失败
  on_discovery_error: "warn"

  # 工具刷新间隔（秒），0 表示不自动刷新
  refresh_interval: 0

  # 是否启用 MCP 工具缓存
  enable_cache: true

  # 缓存 TTL（秒）
  cache_ttl: 300
```

### 配置示例

#### 严格模式（发现失败则启动失败）

```yaml
global:
  auto_discover_on_startup: true
  on_discovery_error: "fail"
  enable_cache: true
  cache_ttl: 300
```

#### 宽松模式（发现失败继续启动）

```yaml
global:
  auto_discover_on_startup: true
  on_discovery_error: "ignore"
  enable_cache: true
  cache_ttl: 300
```

---

## 安全配置

安全配置用于控制工具执行的权限和审计。

### 参数说明

```yaml
security:
  # 是否要求所有 MCP 工具调用都需要审批
  require_approval: false

  # 高风险工具是否需要审批
  require_approval_for_high_risk: true

  # 是否启用审计日志
  enable_audit: true

  # 审计日志最大条目数
  max_audit_entries: 10000
```

### 配置示例

#### 高安全性配置

```yaml
security:
  require_approval: true
  require_approval_for_high_risk: true
  enable_audit: true
  max_audit_entries: 50000
```

#### 标准安全配置

```yaml
security:
  require_approval: false
  require_approval_for_high_risk: true
  enable_audit: true
  max_audit_entries: 10000
```

---

## 性能配置

性能配置用于优化 MCP 工具的执行效率。

### 参数说明

```yaml
performance:
  # 最大并发 MCP 请求数
  max_concurrent_requests: 10

  # 请求超时（秒）
  default_timeout: 30.0

  # 连接池大小
  connection_pool_size: 10
```

### 配置示例

#### 高吞吐量配置

```yaml
performance:
  max_concurrent_requests: 50
  default_timeout: 60.0
  connection_pool_size: 50
```

#### 低资源配置

```yaml
performance:
  max_concurrent_requests: 5
  default_timeout: 15.0
  connection_pool_size: 5
```

---

## 监控配置

监控配置用于启用健康检查和性能指标收集。

### 参数说明

```yaml
monitoring:
  # 是否启用健康检查
  enable_health_check: true

  # 健康检查间隔（秒）
  health_check_interval: 60

  # 是否收集性能指标
  collect_metrics: true

  # 指标收集间隔（秒）
  metrics_interval: 30
```

### 配置示例

#### 完整监控配置

```yaml
monitoring:
  enable_health_check: true
  health_check_interval: 30
  collect_metrics: true
  metrics_interval: 15
```

#### 最小监控配置

```yaml
monitoring:
  enable_health_check: false
  collect_metrics: false
```

---

## 工具过滤规则

工具过滤规则用于选择性地注册工具。

### 参数说明

```yaml
filters:
  # 只注册特定类别的工具
  allowed_categories:
    - "file_system"
    - "database"
    - "web"

  # 排除特定风险级别的工具
  excluded_risk_levels:
    - "critical"

  # 只注册包含特定标签的工具
  required_tags:
    - "safe"

  # 排除包含特定标签的工具
  excluded_tags:
    - "experimental"
```

### 配置示例

#### 只注册安全工具

```yaml
filters:
  excluded_risk_levels:
    - "high"
    - "critical"
  excluded_tags:
    - "experimental"
    - "beta"
```

#### 只注册特定类别

```yaml
filters:
  allowed_categories:
    - "file_system"
    - "database"
```

---

## 常见配置场景

### 场景 1：开发环境

```yaml
mcp_servers:
  - name: "filesystem"
    url: "http://localhost:8001"
    enabled: true
    auto_register: true
    timeout: 30.0
    max_retries: 3

  - name: "database"
    url: "http://localhost:8002"
    enabled: true
    auto_register: true
    timeout: 30.0
    max_retries: 3

global:
  auto_discover_on_startup: true
  on_discovery_error: "warn"
  enable_cache: true
  cache_ttl: 300

security:
  require_approval: false
  require_approval_for_high_risk: false
  enable_audit: false

performance:
  max_concurrent_requests: 10
  default_timeout: 30.0
  connection_pool_size: 10

monitoring:
  enable_health_check: true
  health_check_interval: 60
  collect_metrics: false
```

### 场景 2：生产环境

```yaml
mcp_servers:
  - name: "filesystem"
    url: "http://mcp-fs.prod:8001"
    enabled: true
    auto_register: true
    timeout: 30.0
    max_retries: 5

  - name: "database"
    url: "http://mcp-db.prod:8002"
    enabled: true
    auto_register: true
    timeout: 45.0
    max_retries: 5

  - name: "browser"
    url: "http://mcp-browser.prod:8005"
    enabled: true
    auto_register: true
    timeout: 60.0
    max_retries: 3

global:
  auto_discover_on_startup: true
  on_discovery_error: "fail"
  enable_cache: true
  cache_ttl: 600

security:
  require_approval: false
  require_approval_for_high_risk: true
  enable_audit: true
  max_audit_entries: 100000

performance:
  max_concurrent_requests: 50
  default_timeout: 45.0
  connection_pool_size: 50

monitoring:
  enable_health_check: true
  health_check_interval: 30
  collect_metrics: true
  metrics_interval: 15

filters:
  excluded_risk_levels:
    - "critical"
  excluded_tags:
    - "experimental"
```

### 场景 3：最小化配置

```yaml
mcp_servers:
  - name: "filesystem"
    url: "http://localhost:8001"

global:
  on_discovery_error: "warn"

security:
  enable_audit: false

monitoring:
  enable_health_check: false
```

---

## 最佳实践

### 1. 服务器配置

- **使用有意义的名称**：选择清晰的服务器名称，便于识别和管理
- **设置合理的超时**：根据服务器响应时间设置超时，避免过长或过短
- **启用自动注册**：除非有特殊需求，否则启用 `auto_register`
- **使用标签分类**：为服务器添加标签便于过滤和管理

### 2. 全局配置

- **开发环境**：设置 `on_discovery_error: "warn"` 允许部分失败
- **生产环境**：设置 `on_discovery_error: "fail"` 确保完整性
- **启用缓存**：在生产环境启用缓存提高性能
- **合理设置缓存 TTL**：根据数据变化频率调整

### 3. 安全配置

- **高风险工具审批**：始终为高风险工具启用审批
- **启用审计日志**：在生产环境启用审计以追踪操作
- **定期审查日志**：定期检查审计日志发现异常

### 4. 性能配置

- **监控并发数**：根据系统资源调整最大并发请求数
- **连接池大小**：设置与最大并发数相匹配
- **超时设置**：避免长时间等待，设置合理的超时

### 5. 监控配置

- **启用健康检查**：定期检查服务器健康状态
- **收集指标**：在生产环境收集性能指标
- **设置合理间隔**：平衡监控开销和及时性

### 6. 工具过滤

- **明确允许列表**：优先使用 `allowed_categories` 而非排除列表
- **排除不安全工具**：排除高风险和实验性工具
- **定期审查**：定期审查过滤规则确保适当

---

## 配置验证

### 检查配置文件语法

```bash
# 使用 Python 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('config/mcp_servers.yaml'))"
```

### 查看配置加载状态

应用启动时会输出配置加载信息：

```
INFO: Loaded MCP configuration from config/mcp_servers.yaml
INFO: Initializing 5 MCP servers...
INFO: MCP initialization complete: 5/5 servers connected
```

### 获取 MCP 统计信息

通过 API 获取 MCP 统计信息：

```bash
curl http://localhost:8000/api/v1/mcp/stats
```

响应示例：

```json
{
  "initialized": true,
  "servers": {
    "total_servers": 5,
    "servers": {
      "filesystem": {
        "status": "healthy",
        "tools_count": 5
      },
      "database": {
        "status": "healthy",
        "tools_count": 8
      }
    }
  },
  "mcp_tools_count": 13
}
```

---

## 故障排除

### 配置文件未找到

**症状**：启动时出现 "No MCP configuration file found" 警告

**解决方案**：
1. 确保 `config/mcp_servers.yaml` 存在
2. 检查文件路径是否正确
3. 检查文件权限

### 服务器连接失败

**症状**：启动时出现 "Health check failed for server" 错误

**解决方案**：
1. 确保 MCP 服务器正在运行
2. 检查 URL 是否正确
3. 检查网络连接
4. 检查防火墙设置

### 工具注册失败

**症状**：启动时出现 "Failed to register tool" 错误

**解决方案**：
1. 检查工具定义是否有效
2. 查看详细日志了解失败原因
3. 检查工具过滤规则

---

## 相关文档

- [MCP 故障排除指南](./MCP_TROUBLESHOOTING.md)
- [MCP API 参考](./MCP_API_REFERENCE.md)
- [X-Agent API 参考](../api/API_REFERENCE.md)
