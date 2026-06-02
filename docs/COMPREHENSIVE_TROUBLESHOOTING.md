# X-Agent 故障排除指南

完整的故障排除指南，涵盖常见错误、日志分析、性能诊断和网络问题。

## 目录

- [快速诊断](#快速诊断)
- [安装问题](#安装问题)
- [数据库问题](#数据库问题)
- [API 和服务问题](#api-和服务问题)
- [性能问题](#性能问题)
- [网络问题](#网络问题)
- [日志分析](#日志分析)
- [获取支持](#获取支持)

---

## 快速诊断

### 健康检查

首先运行健康检查来诊断系统状态：

```bash
# 检查 API 健康状态
curl http://localhost:8000/health

# 预期响应：
# {"status": "healthy", "version": "0.1.0"}

# 检查数据库连接
curl http://localhost:8000/health/db

# 检查 Qdrant 连接
curl http://localhost:8000/health/qdrant

# 检查所有依赖
curl http://localhost:8000/health/full
```

### 诊断脚本

运行诊断脚本获取系统信息：

```bash
# 运行完整诊断
python -m backend.app.core.diagnostics

# 生成诊断报告
python -m backend.app.core.diagnostics --report > diagnosis.txt

# 检查特定组件
python -m backend.app.core.diagnostics --component database
python -m backend.app.core.diagnostics --component llm
python -m backend.app.core.diagnostics --component memory
```

---

## 安装问题

### 问题：Python 版本不兼容

**症状**：
```
Error: Python 3.11 or higher required
```

**诊断**：
```bash
python --version
```

**解决方案**：

**Ubuntu/Debian**：
```bash
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv
```

**macOS**：
```bash
brew install python@3.11
```

**Windows**：
1. 访问 [python.org](https://www.python.org/downloads/)
2. 下载 Python 3.11+ 安装程序
3. 运行安装程序，勾选 "Add Python to PATH"

### 问题：虚拟环境激活失败

**症状**：
```
command not found: python
ModuleNotFoundError: No module named 'fastapi'
```

**解决方案**：

**Linux/macOS**：
```bash
source venv/bin/activate
```

**Windows**：
```bash
venv\Scripts\activate
```

### 问题：依赖安装失败

**症状**：
```
ERROR: Could not find a version that satisfies the requirement
```

**解决方案**：

```bash
# 升级 pip
pip install --upgrade pip setuptools wheel

# 清除缓存
pip cache purge

# 重新安装
pip install --no-cache-dir -e ".[dev]"
```

---

## 数据库问题

### 问题：PostgreSQL 连接失败

**症状**：
```
could not connect to server: Connection refused
```

**解决方案**：

```bash
# 使用 Docker
docker-compose up -d postgres

# 或手动启动
sudo systemctl start postgresql

# 测试连接
psql -U xagent -h localhost -d xagent_db
```

### 问题：数据库已存在

**症状**：
```
database "xagent_db" already exists
```

**解决方案**：

```bash
# 删除并重新创建
psql -U postgres -c "DROP DATABASE xagent_db;"
python -m backend.app.core.migration init
```

### 问题：Qdrant 连接失败

**症状**：
```
Failed to connect to Qdrant at http://localhost:6333
```

**解决方案**：

```bash
# 启动 Qdrant
docker-compose up -d qdrant

# 验证
curl http://localhost:6333/health
```

---

## API 和服务问题

### 问题：端口 8000 已被占用

**症状**：
```
Address already in use: ('0.0.0.0', 8000)
```

**解决方案**：

**Linux/macOS**：
```bash
lsof -i :8000
kill -9 <PID>
```

**Windows**：
```bash
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

或使用不同的端口：
```bash
uvicorn backend.app.web:app --port 8001
```

### 问题：API 返回 500 错误

**症状**：
```
Internal Server Error
```

**解决方案**：

```bash
# 启用调试模式
DEBUG=true uvicorn backend.app.web:app --reload

# 检查数据库连接
curl http://localhost:8000/health/db

# 查看详细日志
LOG_LEVEL=DEBUG uvicorn backend.app.web:app
```

### 问题：API 返回 401 未授权

**症状**：
```
401 Unauthorized
```

**解决方案**：

```bash
# 检查 API 密钥
echo $OPENAI_API_KEY

# 在 .env 中设置
OPENAI_API_KEY=sk-...
```

---

## 性能问题

### 问题：API 响应缓慢

**症状**：
```
请求需要 10+ 秒才能完成
```

**解决方案**：

```bash
# 创建数据库索引
docker-compose exec postgres psql -U xagent -d xagent_db -c "
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_agents_name ON agents(name);
"

# 运行 VACUUM
docker-compose exec postgres psql -U xagent -d xagent_db -c "VACUUM ANALYZE;"

# 启用缓存
REDIS_URL=redis://localhost:6379
```

### 问题：内存使用过高

**症状**：
```
内存使用率 > 80%
```

**解决方案**：

```bash
# 清理旧数据
python -m backend.app.core.maintenance cleanup_old_tasks --days 30

# 增加容器内存
# 编辑 docker-compose.yml
mem_limit: 4g
```

### 问题：CPU 使用率过高

**症状**：
```
CPU 使用率 > 90%
```

**解决方案**：

```bash
# 减少并发 Agent 数量
MAX_CONCURRENT_AGENTS=4

# 启用限流
RATE_LIMIT_ENABLED=true
```

---

## 网络问题

### 问题：无法连接到外部 API

**症状**：
```
Connection timeout
```

**解决方案**：

```bash
# 测试网络连接
ping 8.8.8.8

# 检查 DNS
nslookup api.openai.com

# 配置代理（如需要）
export HTTP_PROXY=http://proxy.company.com:8080
```

### 问题：CORS 错误

**症状**：
```
Access to XMLHttpRequest blocked by CORS policy
```

**解决方案**：

```bash
# 在 .env 中配置
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# 重启服务
docker-compose restart backend
```

---

## 日志分析

### 查看日志

```bash
# 查看 API 服务日志
docker-compose logs backend

# 实时查看
docker-compose logs -f backend

# 查看特定时间范围
docker-compose logs --since 2026-05-29T10:00:00 backend

# 查看最后 100 行
docker-compose logs --tail 100 backend
```

### 日志级别

```bash
LOG_LEVEL=DEBUG    # 详细调试信息
LOG_LEVEL=INFO     # 一般信息
LOG_LEVEL=WARNING  # 警告信息
LOG_LEVEL=ERROR    # 错误信息
```

---

## 获取支持

### 支持渠道

1. **GitHub Issues**：https://github.com/x-agent/x-agent-core/issues
2. **GitHub Discussions**：https://github.com/x-agent/x-agent-core/discussions
3. **Email**：support@x-agent.dev

### 提交诊断报告

```bash
# 生成诊断报告
python -m backend.app.core.diagnostics --report > diagnosis.txt

# 收集日志
docker-compose logs > logs.txt

# 打包文件
tar -czf xagent_diagnostics.tar.gz diagnosis.txt logs.txt
```

---

**最后更新**：2026年5月29日
