# X-Agent V2 部署资源索引

## 概述

本索引文件汇总了 X-Agent 新架构（Agent V2）部署所需的所有资源、文档和工具。

**部署版本**: 0.2.0  
**发布日期**: 2026-05-26  
**状态**: 准备就绪

---

## 快速开始

### 1. 阅读文档（5 分钟）
1. 先读 [部署快速参考](DEPLOYMENT_QUICK_REFERENCE.md) - 了解基本概念
2. 再读 [部署总结](DEPLOYMENT_SUMMARY.md) - 了解部署包内容

### 2. 准备环境（30 分钟）
```bash
# 运行健康检查
python scripts/health_check.py

# 备份数据
pg_dump -h localhost -U xagent xagent > backup_$(date +%Y%m%d_%H%M%S).sql
redis-cli BGSAVE
```

### 3. 执行部署（30-60 分钟）
```bash
# 运行自动化部署脚本
python scripts/deploy_agent_v2.py

# 监控部署进度
watch -n 5 'curl -s http://localhost:8000/admin/metrics/execution | jq'
```

### 4. 验证部署（10 分钟）
```bash
# 运行健康检查
python scripts/health_check.py

# 检查执行指标
curl http://localhost:8000/admin/metrics/execution
```

---

## 文档导航

### 部署文档

| 文档 | 用途 | 阅读时间 |
|------|------|---------|
| [DEPLOYMENT_QUICK_REFERENCE.md](DEPLOYMENT_QUICK_REFERENCE.md) | 快速参考，常用命令 | 5 分钟 |
| [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md) | 部署包总结，集成指南 | 10 分钟 |
| [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) | 完整检查清单，详细步骤 | 20 分钟 |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | 详细部署指南，故障排查 | 30 分钟 |

### 推荐阅读顺序

```
新手用户:
  1. DEPLOYMENT_QUICK_REFERENCE.md (快速了解)
  2. DEPLOYMENT_SUMMARY.md (了解部署包)
  3. DEPLOYMENT_CHECKLIST.md (按清单部署)
  4. DEPLOYMENT_GUIDE.md (遇到问题时查阅)

有经验的运维:
  1. DEPLOYMENT_QUICK_REFERENCE.md (快速查阅)
  2. DEPLOYMENT_GUIDE.md (灰度策略和监控)
  3. DEPLOYMENT_CHECKLIST.md (验证清单)

开发人员:
  1. DEPLOYMENT_SUMMARY.md (了解集成方式)
  2. 相关源代码 (feature_flags.py, agent_compat.py)
  3. DEPLOYMENT_GUIDE.md (架构设计部分)
```

---

## 核心模块

### 1. 特性开关系统

**文件**: `backend/app/core/feature_flags.py`

**功能**:
- 全局启用/禁用 Agent V2
- 灰度发布（按百分比）
- 按租户/用户启用
- 一致性哈希确保用户路由一致

**关键类**:
- `FeatureFlag`: 特性开关枚举
- `FeatureFlagManager`: 特性开关管理器
- `get_feature_flag_manager()`: 获取全局实例

**使用示例**:
```python
from backend.app.core.feature_flags import get_feature_flag_manager, FeatureFlag

manager = get_feature_flag_manager()
if manager.is_enabled(FeatureFlag.USE_AGENT_V2, tenant_id="tenant1"):
    # 使用 Agent V2
    pass
```

### 2. 兼容层

**文件**: `backend/app/core/agent_compat.py`

**功能**:
- 根据特性开关路由请求到 V1 或 V2
- 收集执行统计
- 支持自动回滚
- 提供调试信息

**关键类**:
- `AgentCompatibilityLayer`: 兼容层实现
- `get_compatibility_layer()`: 获取全局实例

**使用示例**:
```python
from backend.app.core.agent_compat import get_compatibility_layer

layer = get_compatibility_layer()
response = await layer.execute(context, task, tenant_id="tenant1")
```

### 3. 监控配置

**文件**: `backend/app/core/monitoring_config.py`

**功能**:
- 定义执行、性能、数据库、缓存指标
- 定义告警规则
- 提供 Prometheus 配置模板
- 提供 Grafana 仪表板配置

**关键配置**:
- `EXECUTION_METRICS`: 执行指标定义
- `ALERT_RULES`: 告警规则定义
- `DASHBOARD_CONFIG`: 仪表板配置
- `SLO_CONFIG`: SLO 目标定义

---

## 部署脚本

### 1. 自动化部署脚本

**文件**: `scripts/deploy_agent_v2.py`

**功能**:
- 执行部署前检查
- 运行数据库迁移
- 执行灰度发布（10% -> 25% -> 50% -> 75% -> 100%）
- 监控关键指标
- 自动回滚

**使用方式**:
```bash
python scripts/deploy_agent_v2.py
```

**配置选项**:
```python
config = DeploymentConfig(
    api_url="http://localhost:8000",
    initial_rollout_percentage=10,
    rollout_increment=10,
    rollout_interval_seconds=300,
    error_threshold_percentage=5.0,
)
```

**预期输出**:
```
============================================================
PHASE: Pre-Deployment Checks
============================================================
Service readiness check 1/5...
All services are ready
Pre-deployment checks passed

============================================================
PHASE: Database Migrations
============================================================
Creating migrations table...
Database migrations completed

============================================================
PHASE: Gradual Rollout
============================================================
Setting rollout to 10%...
Monitoring at 10% for 300s...
...
Gradual rollout completed successfully

============================================================
DEPLOYMENT SUCCESSFUL
============================================================
```

### 2. 健康检查脚本

**文件**: `scripts/health_check.py`

**功能**:
- 检查 API 健康状态
- 检查数据库连接
- 检查 Redis 连接
- 检查 Qdrant 连接
- 检查特性开关
- 检查指标端点

**使用方式**:
```bash
python scripts/health_check.py
```

**预期输出**:
```
Running health checks...

✓ API: API is responding
✓ Database: Database is responding
✓ Redis: Redis is responding
✓ Qdrant: Qdrant is responding
✓ Feature Flags: Feature flags are accessible
✓ Metrics: Metrics are available

==================================================
Health Check Summary
==================================================
Total checks: 6
Healthy: 6
Degraded: 0
Unhealthy: 0
Overall status: healthy
==================================================
```

---

## 灰度发布流程

### 阶段划分

| 阶段 | 灰度比例 | 持续时间 | 监控项 | 回滚条件 |
|------|---------|---------|--------|---------|
| 初始化 | 10% | 5 分钟 | 错误率、响应时间 | 错误率 > 5% |
| 扩展 | 25% | 5 分钟 | 错误率、性能 | 错误率 > 5% |
| 主流量 | 50% | 5 分钟 | 错误率、性能 | 错误率 > 5% |
| 大部分 | 75% | 5 分钟 | 错误率、稳定性 | 错误率 > 5% |
| 完全切换 | 100% | 持续 | 全面监控 | 错误率 > 5% |

### 手动灰度发布

```bash
# 启用 10% 灰度
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 10}'

# 监控 5 分钟...

# 增加到 25% 灰度
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 25}'

# 继续监控和增加...
```

---

## 监控和告警

### 关键指标

| 指标 | 目标 | 告警阈值 | 说明 |
|------|------|---------|------|
| Agent V2 错误率 | < 1% | > 5% | 执行失败比例 |
| API 响应时间 (p95) | < 500ms | > 1000ms | 95 分位响应时间 |
| 数据库连接池使用率 | < 70% | > 90% | 连接池饱和度 |
| Redis 内存使用率 | < 70% | > 85% | 缓存内存使用 |
| 消息队列延迟 | < 1s | > 5s | 任务处理延迟 |

### 监控命令

```bash
# 实时监控执行统计
watch -n 5 'curl -s http://localhost:8000/admin/metrics/execution | jq'

# 查看 Agent V2 日志
docker-compose logs -f backend | grep "Agent V2"

# 检查错误日志
docker-compose logs backend | grep ERROR

# 获取完整指标
curl http://localhost:8000/admin/metrics/execution
curl http://localhost:8000/admin/metrics/performance
curl http://localhost:8000/admin/metrics/database
```

---

## 回滚流程

### 自动回滚

系统在以下情况下自动回滚：
- 错误率 > 5% 持续 5 分钟
- 响应时间 p95 > 1000ms 持续 5 分钟
- 数据库连接池使用率 > 90%
- 健康检查失败 3 次

### 手动回滚

```bash
# 立即禁用 Agent V2
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "rollout_percentage": 0}'

# 验证回滚
curl http://localhost:8000/admin/metrics/execution

# 检查所有流量都使用 Agent V1
curl http://localhost:8000/admin/metrics/execution | jq '.v1_executions'
```

### 数据恢复

```bash
# 从备份恢复数据库
psql -h localhost -U xagent xagent < backup_YYYYMMDD_HHMMSS.sql

# 清空 Redis 缓存
redis-cli FLUSHALL

# 重启服务
docker-compose restart backend
```

---

## 故障排查

### 常见问题

#### Q1: Agent V2 执行失败

**检查步骤**:
1. 查看日志: `docker-compose logs backend | grep ERROR`
2. 检查数据库: `psql -h localhost -U xagent -d xagent -c "SELECT 1"`
3. 检查 Redis: `redis-cli ping`
4. 检查 Qdrant: `curl http://localhost:6333/health`

**解决方案**:
- 检查连接字符串
- 重启服务
- 查看详细错误日志

#### Q2: 性能下降

**检查步骤**:
1. 检查资源: `docker stats backend`
2. 检查连接池: `curl http://localhost:8000/admin/metrics/database`
3. 检查缓存: `curl http://localhost:8000/admin/metrics/cache`

**解决方案**:
- 增加资源
- 优化查询
- 清空缓存

#### Q3: 内存泄漏

**检查步骤**:
1. 监控内存: `watch -n 5 'docker stats backend --no-stream'`
2. 检查连接: `docker-compose exec backend netstat -an | grep ESTABLISHED | wc -l`

**解决方案**:
- 重启服务
- 检查代码
- 增加内存

---

## 集成指南

### 1. 集成特性开关到 API

```python
from fastapi import FastAPI
from backend.app.core.feature_flags import get_feature_flag_manager, FeatureFlag

app = FastAPI()

@app.post("/admin/feature-flags/use_agent_v2")
async def update_agent_v2_flag(enabled: bool, rollout_percentage: int = 0):
    manager = get_feature_flag_manager()
    manager.set_flag(FeatureFlag.USE_AGENT_V2, enabled, rollout_percentage)
    return {"status": "updated"}
```

### 2. 集成兼容层到执行流程

```python
from backend.app.core.agent_compat import get_compatibility_layer

async def execute_agent(context, task, tenant_id=None):
    layer = get_compatibility_layer()
    response = await layer.execute(context, task, tenant_id=tenant_id)
    return response
```

### 3. 集成监控指标

```python
from prometheus_client import Counter, Histogram

v2_executions = Counter(
    "agent_v2_executions_total",
    "Total Agent V2 executions",
    ["tenant_id", "status"],
)

v2_executions.labels(tenant_id="tenant1", status="success").inc()
```

---

## 部署检查清单

### 部署前
- [ ] 所有代码已审查
- [ ] 所有测试通过
- [ ] 数据库备份完成
- [ ] Redis 备份完成
- [ ] 环境变量已配置
- [ ] 特性开关已配置
- [ ] 监控告警已配置
- [ ] 团队已通知
- [ ] 回滚计划已准备

### 部署中
- [ ] 健康检查通过
- [ ] 数据库迁移成功
- [ ] 灰度发布按计划进行
- [ ] 监控指标正常
- [ ] 没有异常错误

### 部署后
- [ ] 所有服务运行正常
- [ ] Agent V2 能够执行任务
- [ ] 错误率在预期范围内
- [ ] 性能指标正常
- [ ] 日志记录正确
- [ ] 用户反馈正面

---

## 文件结构

```
X-Agent 原创内核计划/
├── DEPLOYMENT_CHECKLIST.md          # 部署检查清单
├── DEPLOYMENT_GUIDE.md              # 详细部署指南
├── DEPLOYMENT_QUICK_REFERENCE.md    # 快速参考
├── DEPLOYMENT_SUMMARY.md            # 部署总结
├── DEPLOYMENT_INDEX.md              # 本文件
├── backend/
│   └── app/
│       └── core/
│           ├── feature_flags.py      # 特性开关系统
│           ├── agent_compat.py       # 兼容层
│           ├── monitoring_config.py  # 监控配置
│           └── agent_v2/             # Agent V2 实现
│               ├── agent_executor.py
│               ├── state_manager.py
│               └── phases/
└── scripts/
    ├── deploy_agent_v2.py           # 自动化部署脚本
    └── health_check.py              # 健康检查脚本
```

---

## 支持和联系

- **部署负责人**: [姓名] ([邮箱])
- **技术支持**: [邮箱] / [电话]
- **运维团队**: [Slack 频道]
- **紧急情况**: [24/7 热线]

---

## 相关资源

- [Agent V2 架构设计](docs/architecture.md)
- [API 文档](docs/api.md)
- [故障排查指南](docs/troubleshooting.md)
- [性能优化指南](docs/performance.md)

---

**文档版本**: 1.0  
**创建日期**: 2026-05-26  
**最后更新**: 2026-05-26  
**维护者**: X-Agent 团队

---

## 快速链接

- [快速开始](#快速开始)
- [文档导航](#文档导航)
- [核心模块](#核心模块)
- [部署脚本](#部署脚本)
- [灰度发布流程](#灰度发布流程)
- [监控和告警](#监控和告警)
- [回滚流程](#回滚流程)
- [故障排查](#故障排查)
- [集成指南](#集成指南)
- [部署检查清单](#部署检查清单)
