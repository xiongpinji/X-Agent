# MCP 故障排除指南

本指南帮助诊断和解决 X-Agent 中 MCP（Model Context Protocol）相关的常见问题。

## 目录

- [诊断工具](#诊断工具)
- [常见问题](#常见问题)
- [调试技巧](#调试技巧)
- [日志分析](#日志分析)
- [性能优化](#性能优化)
- [高级故障排除](#高级故障排除)

---

## 诊断工具

### 1. 健康检查 API

检查 MCP 系统的整体健康状态：

```bash
curl http://localhost:8000/api/v1/mcp/health
```

响应示例（健康）：

```json
{
  "status": "healthy",
  "servers": {
    "filesystem": {
      "status": "healthy",
      "stats": {
        "tools_count": 5,
        "last_check": "2025-05-29T10:30:00Z"
      }
    },
    "database": {
      "status": "healthy",
      "stats": {
        "tools_count": 8,
        "last_check": "2025-05-29T10:30:00Z"
      }
    }
  }
}
```

响应示例（不健康）：

```json
{
  "status": "degraded",
  "servers": {
    "filesystem": {
      "status": "healthy",
      "stats": {}
    },
    "database": {
      "status": "error",
      "error": "Connection timeout"
    }
  }
}
```

### 2. 统计信息 API

获取详细的 MCP 统计信息：

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
        "tools_count": 5,
        "active_connections": 2,
        "cache_size": 15
      },
      "database": {
        "status": "healthy",
        "tools_count": 8,
        "active_connections": 1,
        "cache_size": 8
      }
    }
  },
  "mcp_tools_count": 13
}
```

### 3. 工具列表 API

列出所有已注册的 MCP 工具：

```bash
curl http://localhost:8000/api/v1/tools?tags=mcp
```

---

## 常见问题

### 问题 1：MCP 管理器未初始化

**症状**：
- 启动日志显示 "MCP manager not initialized"
- 工具执行失败，提示 "MCP manager not initialized"

**原因**：
- 配置文件不存在或路径错误
- 所有 MCP 服务器连接失败
- 配置中 `on_discovery_error` 设置为 "fail"

**解决方案**：

1. 检查配置文件是否存在：
```bash
ls -la config/mcp_servers.yaml
```

2. 验证配置文件格式：
```bash
python -c "import yaml; yaml.safe_load(open('config/mcp_servers.yaml'))"
```

3. 检查启动日志：
```bash
grep -i "mcp" logs/app.log | head -20
```

4. 如果配置正确但仍失败，尝试更改错误处理策略：
```yaml
global:
  on_discovery_error: "warn"  # 改为 "warn" 而非 "fail"
```

---

### 问题 2：服务器连接失败

**症状**：
- 启动日志显示 "Health check failed for server"
- 特定服务器状态为 "error" 或 "unhealthy"

**原因**：
- MCP 服务器未运行
- 服务器 URL 不正确
- 网络连接问题
- 防火墙阻止

**解决方案**：

1. 验证服务器是否运行：
```bash
# 检查服务器是否监听指定端口
netstat -an | grep 8001
# 或使用 curl 测试连接
curl -v http://localhost:8001/health
```

2. 检查配置中的 URL：
```yaml
mcp_servers:
  - name: "filesystem"
    url: "http://localhost:8001"  # 确保 URL 正确
```

3. 测试网络连接：
```bash
ping localhost
curl -I http://localhost:8001
```

4. 检查防火墙规则：
```bash
# Linux
sudo ufw status
# Windows
netsh advfirewall show allprofiles
```

5. 增加超时时间（如果服务器响应慢）：
```yaml
mcp_servers:
  - name: "filesystem"
    url: "http://localhost:8001"
    timeout: 60.0  # 增加到 60 秒
```

---

### 问题 3：工具发现失败

**症状**：
- 启动日志显示 "Discovered 0 tools from server"
- 工具列表为空

**原因**：
- MCP 服务器未正确实现工具列表接口
- 工具被过滤规则排除
- 服务器返回无效的工具定义

**解决方案**：

1. 检查服务器是否支持工具列表：
```bash
curl http://localhost:8001/tools
```

2. 查看详细日志：
```bash
grep -i "discover" logs/app.log
```

3. 检查过滤规则是否过于严格：
```yaml
filters:
  # 注释掉过滤规则进行测试
  # allowed_categories:
  #   - "file_system"
  # excluded_risk_levels:
  #   - "high"
```

4. 验证工具定义格式：
```bash
# 检查服务器返回的工具定义
curl http://localhost:8001/tools | python -m json.tool
```

---

### 问题 4：工具执行失败

**症状**：
- 工具调用返回错误
- 错误信息：`"Tool execution failed"`

**原因**：
- 工具参数不正确
- 工具权限不足
- 服务器内部错误
- 超时

**解决方案**：

1. 检查工具参数：
```bash
# 获取工具定义
curl http://localhost:8000/api/v1/tools/mcp_filesystem_read_file
```

2. 查看详细错误日志：
```bash
grep -i "error\|exception" logs/app.log | tail -50
```

3. 检查权限设置：
```yaml
security:
  require_approval_for_high_risk: true
```

4. 增加超时时间：
```yaml
performance:
  default_timeout: 60.0
```

5. 测试工具调用：
```bash
curl -X POST http://localhost:8000/api/v1/tools/mcp_filesystem_read_file/execute \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/test.txt"}'
```

---

### 问题 5：性能问题

**症状**：
- 工具执行缓慢
- 高 CPU 或内存使用
- 并发请求失败

**原因**：
- 并发限制过低
- 缓存未启用
- 连接池过小
- 服务器过载

**解决方案**：

1. 检查当前性能配置：
```bash
curl http://localhost:8000/api/v1/mcp/stats
```

2. 增加并发限制：
```yaml
performance:
  max_concurrent_requests: 50  # 从 10 增加到 50
  connection_pool_size: 50
```

3. 启用缓存：
```yaml
global:
  enable_cache: true
  cache_ttl: 600  # 10 分钟
```

4. 监控服务器资源：
```bash
# 监控 CPU 和内存
top -p $(pgrep -f "mcp_server")
```

---

### 问题 6：缓存问题

**症状**：
- 工具返回过期数据
- 缓存未生效

**原因**：
- 缓存未启用
- 缓存 TTL 过短
- 缓存键生成错误

**解决方案**：

1. 检查缓存配置：
```yaml
global:
  enable_cache: true
  cache_ttl: 300
```

2. 清除缓存：
```bash
curl -X POST http://localhost:8000/api/v1/mcp/cache/clear
```

3. 查看缓存统计：
```bash
curl http://localhost:8000/api/v1/mcp/cache/stats
```

4. 增加缓存 TTL：
```yaml
global:
  cache_ttl: 600  # 从 300 秒增加到 600 秒
```

---

## 调试技巧

### 1. 启用详细日志

编辑应用配置启用 DEBUG 级别日志：

```python
# backend/app/config.py
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("backend.app.core.mcp")
logger.setLevel(logging.DEBUG)
```

或通过环境变量：

```bash
export LOG_LEVEL=DEBUG
python -m backend.app.main
```

### 2. 查看 MCP 日志

```bash
# 查看所有 MCP 相关日志
grep "MCP\|mcp" logs/app.log

# 查看特定服务器的日志
grep "filesystem" logs/app.log

# 查看错误日志
grep -i "error\|exception" logs/app.log | grep -i "mcp"
```

### 3. 测试单个服务器

创建测试脚本 `test_mcp_server.py`：

```python
import asyncio
from backend.app.core.mcp.client import MCPClient

async def test_server(url: str):
    client = MCPClient(server_url=url)
    
    # 测试连接
    try:
        health = await client.health_check()
        print(f"Health check: {health}")
    except Exception as e:
        print(f"Health check failed: {e}")
    
    # 测试工具列表
    try:
        tools = await client.list_tools()
        print(f"Tools: {tools}")
    except Exception as e:
        print(f"List tools failed: {e}")

# 运行测试
asyncio.run(test_server("http://localhost:8001"))
```

运行测试：

```bash
python test_mcp_server.py
```

### 4. 使用 curl 测试 API

```bash
# 测试健康检查
curl -v http://localhost:8000/api/v1/mcp/health

# 测试统计信息
curl -v http://localhost:8000/api/v1/mcp/stats

# 列出工具
curl -v http://localhost:8000/api/v1/tools?tags=mcp

# 执行工具
curl -X POST http://localhost:8000/api/v1/tools/mcp_filesystem_read_file/execute \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/test.txt"}' \
  -v
```

---

## 日志分析

### 1. 日志位置

- 应用日志：`logs/app.log`
- MCP 日志：`logs/mcp.log`（如果配置）
- 系统日志：`/var/log/syslog`（Linux）

### 2. 关键日志消息

| 消息 | 含义 | 严重性 |
|------|------|--------|
| `Loaded MCP configuration` | 配置加载成功 | INFO |
| `Initializing N MCP servers` | 开始初始化服务器 | INFO |
| `Added MCP server` | 服务器添加成功 | INFO |
| `Health check failed` | 服务器健康检查失败 | ERROR |
| `Failed to discover tools` | 工具发现失败 | ERROR |
| `Registered MCP tool` | 工具注册成功 | INFO |
| `MCP manager initialized` | 管理器初始化成功 | INFO |

### 3. 日志分析示例

查看初始化过程：

```bash
grep -E "Loaded|Initializing|Added|Registered" logs/app.log
```

查看错误：

```bash
grep -i "error\|failed\|exception" logs/app.log
```

查看特定服务器的活动：

```bash
grep "filesystem" logs/app.log
```

查看最近的 N 条日志：

```bash
tail -100 logs/app.log
```

---

## 性能优化

### 1. 连接池优化

```yaml
performance:
  # 根据并发需求调整
  max_concurrent_requests: 50
  connection_pool_size: 50
```

**建议**：
- 开发环境：10-20
- 生产环境：50-100
- 高并发场景：100+

### 2. 缓存优化

```yaml
global:
  enable_cache: true
  cache_ttl: 600  # 根据数据变化频率调整
```

**建议**：
- 静态数据：600-3600 秒
- 动态数据：60-300 秒
- 实时数据：0（禁用缓存）

### 3. 超时优化

```yaml
mcp_servers:
  - name: "filesystem"
    timeout: 30.0  # 根据操作类型调整
```

**建议**：
- 快速操作（读取）：10-30 秒
- 中等操作（写入）：30-60 秒
- 长时间操作（浏览器）：60-120 秒

### 4. 并发优化

```yaml
performance:
  max_concurrent_requests: 50
```

**建议**：
- 监控实际并发数
- 根据服务器容量调整
- 避免过度并发导致服务器过载

### 5. 监控和调优

启用性能指标收集：

```yaml
monitoring:
  collect_metrics: true
  metrics_interval: 15
```

查看性能指标：

```bash
curl http://localhost:8000/api/v1/mcp/metrics
```

---

## 高级故障排除

### 1. 网络问题诊断

```bash
# 检查 DNS 解析
nslookup localhost

# 检查网络连接
ping localhost

# 检查端口监听
netstat -an | grep 8001

# 使用 tcpdump 捕获流量
sudo tcpdump -i lo port 8001
```

### 2. 内存泄漏检测

```bash
# 监控内存使用
watch -n 1 'ps aux | grep python'

# 使用 memory_profiler
pip install memory-profiler
python -m memory_profiler backend/app/main.py
```

### 3. 死锁检测

```bash
# 查看线程状态
python -c "import sys; sys.settrace(lambda *args: None); import pdb; pdb.set_trace()"

# 使用 threading 模块检查
python -c "import threading; print(threading.enumerate())"
```

### 4. 配置验证

```bash
# 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('config/mcp_servers.yaml')); print('OK')"

# 验证配置内容
python -c "
import yaml
config = yaml.safe_load(open('config/mcp_servers.yaml'))
print('Servers:', len(config.get('mcp_servers', [])))
for server in config.get('mcp_servers', []):
    print(f\"  - {server['name']}: {server['url']}\")
"
```

### 5. 服务器日志检查

检查 MCP 服务器的日志：

```bash
# 查看服务器日志
tail -f /var/log/mcp-filesystem.log

# 查看服务器错误
grep -i "error" /var/log/mcp-filesystem.log
```

---

## 获取帮助

### 1. 收集诊断信息

运行诊断脚本收集系统信息：

```bash
# 创建诊断报告
cat > diagnose.sh << 'EOF'
#!/bin/bash
echo "=== System Info ==="
uname -a
echo ""
echo "=== Python Version ==="
python --version
echo ""
echo "=== MCP Configuration ==="
cat config/mcp_servers.yaml
echo ""
echo "=== MCP Health ==="
curl -s http://localhost:8000/api/v1/mcp/health | python -m json.tool
echo ""
echo "=== Recent Logs ==="
tail -50 logs/app.log
EOF

chmod +x diagnose.sh
./diagnose.sh > diagnostic_report.txt
```

### 2. 提交问题

提交问题时包含：
- 诊断报告（见上）
- 完整的错误日志
- 配置文件（隐藏敏感信息）
- 重现步骤

### 3. 相关文档

- [MCP 配置指南](MCP_CONFIGURATION_GUIDE.md)
- [MCP API 参考](MCP_API_REFERENCE.md)
- [X-Agent 故障排除](TROUBLESHOOTING.md)

---

## 快速参考

| 问题 | 命令 |
|------|------|
| 检查健康状态 | `curl http://localhost:8000/api/v1/mcp/health` |
| 查看统计信息 | `curl http://localhost:8000/api/v1/mcp/stats` |
| 列出工具 | `curl http://localhost:8000/api/v1/tools?tags=mcp` |
| 查看日志 | `tail -f logs/app.log` |
| 验证配置 | `python -c "import yaml; yaml.safe_load(open('config/mcp_servers.yaml'))"` |
| 测试服务器 | `curl http://localhost:8001/health` |
| 清除缓存 | `curl -X POST http://localhost:8000/api/v1/mcp/cache/clear` |
