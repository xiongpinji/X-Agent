# X-Agent 故障排除指南

**版本**: 1.0.0  
**最后更新**: 2026-05-27

---

## 目录

1. [常见问题分类](#常见问题分类)
2. [安装问题](#安装问题)
3. [配置问题](#配置问题)
4. [运行时错误](#运行时错误)
5. [性能问题](#性能问题)
6. [网络问题](#网络问题)
7. [日志分析指南](#日志分析指南)
8. [调试工具使用](#调试工具使用)

---

## 常见问题分类

### 问题分类表

| 类别 | 症状 | 可能原因 | 优先级 |
|------|------|--------|-------|
| 安装 | 依赖安装失败 | 版本冲突、网络问题 | 高 |
| 配置 | 服务无法启动 | 环境变量缺失、配置错误 | 高 |
| 运行时 | 任务执行失败 | 代码错误、资源不足 | 中 |
| 性能 | 响应缓慢 | 数据库查询慢、内存泄漏 | 中 |
| 网络 | 连接超时 | 网络不稳定、防火墙阻止 | 低 |

---

## 安装问题

### 问题 1: Python 版本不兼容

**症状**:
```
ERROR: Python 3.9 is not supported. Requires Python 3.11+
```

**诊断步骤**:
```bash
# 检查 Python 版本
python --version

# 检查可用的 Python 版本
python3.11 --version
```

**解决方案**:
```bash
# 安装 Python 3.11
sudo apt install python3.11 python3.11-venv

# 使用特定版本创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate
```

### 问题 2: 依赖安装失败

**症状**:
```
ERROR: Could not find a version that satisfies the requirement
```

**诊断步骤**:
```bash
# 检查网络连接
ping pypi.org

# 检查 pip 配置
pip config list

# 尝试升级 pip
pip install --upgrade pip
```

**解决方案**:
```bash
# 使用国内镜像源
pip install -i https://mirrors.aliyun.com/pypi/simple/ -e ".[dev]"

# 或配置 pip 配置文件
cat > ~/.pip/pip.conf << EOF
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
EOF
```

### 问题 3: PostgreSQL 连接失败

**症状**:
```
psycopg2.OperationalError: could not connect to server
```

**诊断步骤**:
```bash
# 检查 PostgreSQL 服务状态
sudo systemctl status postgresql

# 检查 PostgreSQL 监听端口
sudo netstat -tlnp | grep postgres

# 测试连接
psql -h localhost -U postgres -d postgres
```

**解决方案**:
```bash
# 启动 PostgreSQL 服务
sudo systemctl start postgresql

# 检查 PostgreSQL 配置
sudo nano /etc/postgresql/14/main/postgresql.conf
# 确保 listen_addresses = '*'

# 检查 pg_hba.conf
sudo nano /etc/postgresql/14/main/pg_hba.conf
# 添加本地连接规则
```

---

## 配置问题

### 问题 1: 环境变量缺失

**症状**:
```
KeyError: 'DATABASE_URL'
```

**诊断步骤**:
```bash
# 检查环境变量
env | grep DATABASE_URL

# 检查 .env 文件
cat .env
```

**解决方案**:
```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件
nano .env

# 验证环境变量
source .env
echo $DATABASE_URL
```

### 问题 2: 数据库初始化失败

**症状**:
```
ERROR: relation "agents" does not exist
```

**诊断步骤**:
```bash
# 检查数据库是否存在
psql -l | grep xagent

# 检查表是否存在
psql -d xagent -c "\dt"
```

**解决方案**:
```bash
# 重新初始化数据库
python -m backend.app.core.migration init

# 或手动创建数据库
createdb xagent
python -m backend.app.core.migration upgrade
```

### 问题 3: API 密钥无效

**症状**:
```
401 Unauthorized: Invalid API key
```

**诊断步骤**:
```bash
# 检查 API 密钥
echo $OPENAI_API_KEY

# 测试 API 密钥
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

**解决方案**:
```bash
# 更新 API 密钥
export OPENAI_API_KEY="your_new_key"

# 或在 .env 中更新
nano .env
# OPENAI_API_KEY=your_new_key

# 重启应用
systemctl restart x-agent-backend
```

---

## 运行时错误

### 问题 1: Agent 执行超时

**症状**:
```
TimeoutError: Task execution exceeded 300 seconds
```

**诊断步骤**:
```bash
# 查看 Agent 日志
docker logs x-agent-backend | grep "timeout"

# 检查任务执行时间
curl http://localhost:8000/api/v1/agents/agent_123/runs/run_456
```

**解决方案**:
```python
# 增加超时时间
agent.run(
    task="...",
    timeout=600  # 10 分钟
)

# 或在配置中设置
# config/production.yaml
server:
  timeout: 600
```

### 问题 2: 内存不足

**症状**:
```
MemoryError: Unable to allocate memory
```

**诊断步骤**:
```bash
# 检查系统内存
free -h

# 检查进程内存使用
ps aux | grep python

# 监控内存使用
watch -n 1 'free -h'
```

**解决方案**:
```bash
# 增加虚拟内存
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 或优化应用内存使用
# 在代码中添加内存监控
import tracemalloc
tracemalloc.start()
```

### 问题 3: 数据库连接池耗尽

**症状**:
```
QueuePool limit exceeded with overflow
```

**诊断步骤**:
```bash
# 检查数据库连接数
psql -d xagent -c "SELECT count(*) FROM pg_stat_activity;"

# 检查连接池配置
grep -i "pool" .env
```

**解决方案**:
```python
# 增加连接池大小
engine = create_engine(
    DATABASE_URL,
    pool_size=30,
    max_overflow=50
)

# 或在配置中设置
# config/production.yaml
database:
  pool_size: 30
  max_overflow: 50
```

---

## 性能问题

### 问题 1: API 响应缓慢

**症状**:
```
Response time > 5 seconds
```

**诊断步骤**:
```bash
# 使用 curl 测试响应时间
time curl http://localhost:8000/api/v1/agents

# 查看 Prometheus 指标
curl http://localhost:9090/api/v1/query?query=http_request_duration_seconds

# 查看数据库查询时间
# 在 PostgreSQL 中启用日志
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();
```

**解决方案**:
```python
# 添加缓存
from functools import lru_cache

@lru_cache(maxsize=1024)
def get_agent(agent_id: str):
    return db.query(Agent).filter(Agent.id == agent_id).first()

# 或使用 Redis 缓存
from redis import Redis
cache = Redis(host='localhost', port=6379)
```

### 问题 2: 数据库查询慢

**症状**:
```
Query execution time > 1 second
```

**诊断步骤**:
```bash
# 分析查询计划
EXPLAIN ANALYZE SELECT * FROM agents WHERE status = 'active';

# 查看慢查询日志
tail -f /var/log/postgresql/postgresql.log | grep "duration"
```

**解决方案**:
```sql
-- 添加索引
CREATE INDEX idx_agent_status ON agents(status);
CREATE INDEX idx_agent_created_at ON agents(created_at DESC);

-- 分析表
ANALYZE agents;

-- 查看索引使用情况
SELECT * FROM pg_stat_user_indexes;
```

### 问题 3: 内存泄漏

**症状**:
```
Memory usage continuously increases
```

**诊断步骤**:
```python
# 使用 memory_profiler
from memory_profiler import profile

@profile
def my_function():
    large_list = [i for i in range(1000000)]
    return sum(large_list)

# 运行分析
python -m memory_profiler script.py
```

**解决方案**:
```python
# 及时释放资源
import gc

def process_large_data():
    data = load_large_data()
    result = process(data)
    del data  # 显式删除
    gc.collect()  # 强制垃圾回收
    return result

# 或使用上下文管理器
with get_connection() as conn:
    result = conn.execute(query)
    # 自动释放连接
```

---

## 网络问题

### 问题 1: 连接超时

**症状**:
```
ConnectionTimeout: Connection to server timed out
```

**诊断步骤**:
```bash
# 测试网络连接
ping api.x-agent.dev

# 检查 DNS 解析
nslookup api.x-agent.dev

# 测试端口连接
telnet api.x-agent.dev 443

# 查看网络统计
netstat -an | grep ESTABLISHED
```

**解决方案**:
```bash
# 增加连接超时时间
curl --connect-timeout 30 http://localhost:8000

# 或在代码中设置
import requests
requests.get(url, timeout=30)

# 检查防火墙规则
sudo ufw status
sudo ufw allow 8000/tcp
```

### 问题 2: DNS 解析失败

**症状**:
```
Name or service not known
```

**诊断步骤**:
```bash
# 检查 DNS 配置
cat /etc/resolv.conf

# 测试 DNS 解析
dig api.x-agent.dev
nslookup api.x-agent.dev
```

**解决方案**:
```bash
# 更新 DNS 配置
sudo nano /etc/resolv.conf
# nameserver 8.8.8.8
# nameserver 8.8.4.4

# 或使用 systemd-resolved
sudo systemctl restart systemd-resolved
```

---

## 日志分析指南

### 日志位置

```
/var/log/x-agent/
├── backend.log          # 后端应用日志
├── worker.log           # 工作流处理器日志
├── postgresql.log       # 数据库日志
└── nginx.log            # Web 服务器日志
```

### 查看日志

```bash
# 实时查看日志
tail -f /var/log/x-agent/backend.log

# 查看最后 100 行
tail -n 100 /var/log/x-agent/backend.log

# 搜索特定错误
grep "ERROR" /var/log/x-agent/backend.log

# 按时间范围查看
sed -n '/2026-05-27 10:00/,/2026-05-27 11:00/p' /var/log/x-agent/backend.log
```

### 日志级别

| 级别 | 含义 | 示例 |
|------|------|------|
| DEBUG | 调试信息 | 函数调用、变量值 |
| INFO | 一般信息 | 服务启动、请求处理 |
| WARNING | 警告信息 | 性能下降、资源不足 |
| ERROR | 错误信息 | 异常、失败操作 |
| CRITICAL | 严重错误 | 系统崩溃、数据丢失 |

### 日志分析示例

```bash
# 统计错误数量
grep "ERROR" /var/log/x-agent/backend.log | wc -l

# 查看最常见的错误
grep "ERROR" /var/log/x-agent/backend.log | cut -d: -f3 | sort | uniq -c | sort -rn

# 查看特定时间段的错误
grep "2026-05-27 10:" /var/log/x-agent/backend.log | grep "ERROR"

# 导出日志用于分析
grep "ERROR" /var/log/x-agent/backend.log > errors.txt
```

---

## 调试工具使用

### 1. Python 调试器 (pdb)

```python
import pdb

def my_function():
    x = 10
    pdb.set_trace()  # 在此处暂停
    y = x + 5
    return y

# 调试命令
# l - 列出代码
# n - 执行下一行
# s - 进入函数
# c - 继续执行
# p x - 打印变量
# h - 帮助
```

### 2. 日志调试

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def my_function():
    logger.debug("Starting function")
    logger.info("Processing data")
    logger.warning("Low memory")
    logger.error("Operation failed")
```

### 3. 性能分析

```python
import cProfile
import pstats

def my_function():
    # 代码...
    pass

# 分析性能
profiler = cProfile.Profile()
profiler.enable()
my_function()
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

### 4. 网络调试

```bash
# 使用 tcpdump 捕获网络流量
sudo tcpdump -i eth0 -w capture.pcap

# 使用 Wireshark 分析
wireshark capture.pcap

# 使用 curl 调试 HTTP
curl -v http://localhost:8000/api/v1/agents
```

---

## 获取帮助

- **文档**: [完整文档](README.md)
- **GitHub Issues**: [报告问题](https://github.com/x-agent/x-agent-core/issues)
- **讨论区**: [社区讨论](https://github.com/x-agent/x-agent-core/discussions)
- **邮件支持**: support@x-agent.dev

---

**X-Agent 故障排除指南** - 快速解决常见问题
