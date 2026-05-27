# Agent V2 部署快速参考

## 快速命令

### 部署前检查
```bash
# 检查所有服务健康状态
./scripts/health_check.sh

# 备份数据库
pg_dump -h localhost -U xagent xagent > backup_$(date +%Y%m%d_%H%M%S).sql

# 备份 Redis
redis-cli BGSAVE
```

### 启动部署
```bash
# 运行自动化部署脚本
python scripts/deploy_agent_v2.py

# 或手动启用灰度发布
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 10}'
```

### 监控部署
```bash
# 实时监控执行统计
watch -n 5 'curl -s http://localhost:8000/admin/metrics/execution | jq'

# 查看日志
docker-compose logs -f backend | grep "Agent V2"

# 检查错误
docker-compose logs backend | grep ERROR
```

### 回滚
```bash
# 立即禁用 Agent V2
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "rollout_percentage": 0}'

# 验证回滚
curl http://localhost:8000/admin/metrics/execution
```

---

## 灰度发布时间表

| 时间 | 灰度比例 | 监控项 | 预期结果 |
|------|---------|--------|---------|
| T+0 | 10% | 错误率、响应时间 | 错误率 < 1% |
| T+5m | 25% | 错误率、响应时间 | 错误率 < 2% |
| T+10m | 50% | 错误率、性能 | 错误率 < 3% |
| T+15m | 75% | 错误率、稳定性 | 错误率 < 4% |
| T+20m | 100% | 全面监控 | 错误率 < 5% |

---

## 关键指标

### 执行指标
- `v1_executions`: Agent V1 执行次数
- `v2_executions`: Agent V2 执行次数
- `v1_errors`: Agent V1 错误次数
- `v2_errors`: Agent V2 错误次数

### 性能指标
- `execution_time_p50`: 执行时间中位数 (目标: < 200ms)
- `execution_time_p95`: 执行时间 95 分位数 (目标: < 500ms)
- `execution_time_p99`: 执行时间 99 分位数 (目标: < 1000ms)

### 资源指标
- `memory_usage`: 内存使用量 (目标: < 500MB)
- `cpu_usage`: CPU 使用率 (目标: < 50%)
- `db_connections`: 数据库连接数 (目标: < 70%)

---

## 故障排查

### 问题: Agent V2 执行失败

**检查步骤**:
1. 查看日志: `docker-compose logs backend | grep ERROR`
2. 检查数据库: `psql -h localhost -U xagent -d xagent -c "SELECT 1"`
3. 检查 Redis: `redis-cli ping`
4. 检查 Qdrant: `curl http://localhost:6333/health`

**解决方案**:
- 重启服务: `docker-compose restart backend`
- 清空缓存: `redis-cli FLUSHALL`
- 回滚: 禁用 Agent V2 特性开关

### 问题: 性能下降

**检查步骤**:
1. 检查资源: `docker stats backend`
2. 检查连接池: `curl http://localhost:8000/admin/metrics/database`
3. 检查缓存: `curl http://localhost:8000/admin/metrics/cache`

**解决方案**:
- 增加资源
- 优化查询
- 清空缓存
- 回滚

### 问题: 内存泄漏

**检查步骤**:
1. 监控内存: `watch -n 5 'docker stats backend --no-stream'`
2. 检查连接: `docker-compose exec backend netstat -an | grep ESTABLISHED | wc -l`

**解决方案**:
- 重启服务
- 检查代码
- 增加内存

---

## 文件位置

| 文件 | 位置 | 说明 |
|------|------|------|
| 特性开关 | `backend/app/core/feature_flags.py` | 特性开关实现 |
| 兼容层 | `backend/app/core/agent_compat.py` | V1/V2 路由层 |
| 部署脚本 | `scripts/deploy_agent_v2.py` | 自动化部署 |
| 部署清单 | `DEPLOYMENT_CHECKLIST.md` | 部署检查清单 |
| 部署指南 | `DEPLOYMENT_GUIDE.md` | 详细部署指南 |
| 监控配置 | `backend/app/core/monitoring_config.py` | 监控指标定义 |

---

## 联系方式

- **部署负责人**: [姓名] ([邮箱])
- **技术支持**: [邮箱] / [电话]
- **运维团队**: [Slack 频道]
- **紧急情况**: [24/7 热线]

---

## 相关文档

- [部署清单](DEPLOYMENT_CHECKLIST.md)
- [部署指南](DEPLOYMENT_GUIDE.md)
- [架构设计](docs/architecture.md)
- [API 文档](docs/api.md)

---

**最后更新**: 2026-05-26  
**版本**: 1.0
