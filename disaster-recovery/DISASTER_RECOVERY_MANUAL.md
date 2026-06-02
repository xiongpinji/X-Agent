# X-Agent 灾难恢复手册

**版本**: 1.0  
**最后更新**: 2026-05-28  
**用途**: 运维团队在灾难发生时的操作指南

---

## 目录

1. [快速参考](#快速参考)
2. [故障诊断](#故障诊断)
3. [故障转移操作](#故障转移操作)
4. [数据恢复操作](#数据恢复操作)
5. [验证与回切](#验证与回切)
6. [常见问题](#常见问题)

---

## 快速参考

### 紧急联系方式

```
值班工程师: 13800138000 (24/7)
DRP负责人: 13800138001
基础设施主管: 13800138002
数据库管理员: 13800138003
```

### 快速命令

```bash
# 检查系统状态
./scripts/dr/health-check.sh

# 执行自动故障转移
./scripts/dr/failover.sh --auto

# 执行手动故障转移
./scripts/dr/failover.sh --manual --region us-west

# 验证恢复
./scripts/dr/verify-recovery.sh

# 查看恢复日志
tail -f /var/log/xagent/disaster-recovery.log
```

---

## 故障诊断

### 1. 应用服务故障诊断

#### 症状检查清单

```bash
# 检查应用进程
docker ps | grep xagent-api

# 检查应用日志
docker logs xagent-api | tail -100

# 检查资源使用
docker stats xagent-api

# 检查网络连接
netstat -an | grep 8000

# 检查端口
curl -v http://localhost:8000/health
```

#### 常见原因与解决方案

| 症状 | 可能原因 | 解决方案 |
|------|--------|--------|
| 应用进程不存在 | 崩溃或被杀死 | 重启应用: `docker restart xagent-api` |
| 内存溢出 | 内存泄漏 | 检查日志，重启应用 |
| CPU过高 | 死循环或高负载 | 检查日志，分析代码 |
| 连接超时 | 网络问题 | 检查网络配置 |
| 数据库连接失败 | 数据库不可用 | 检查数据库状态 |

### 2. 数据库故障诊断

#### PostgreSQL诊断

```bash
# 检查数据库连接
psql -h localhost -U xagent -d xagent_db -c "SELECT version();"

# 检查复制状态
psql -c "SELECT * FROM pg_stat_replication;"

# 检查磁盘空间
psql -c "SELECT pg_database.datname, pg_size_pretty(pg_database_size(pg_database.datname)) FROM pg_database;"

# 检查连接数
psql -c "SELECT count(*) FROM pg_stat_activity;"

# 检查慢查询
psql -c "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# 检查表大小
psql -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"
```

#### Redis诊断

```bash
# 检查连接
redis-cli -h localhost -p 6379 PING

# 检查内存使用
redis-cli INFO memory

# 检查复制状态
redis-cli INFO replication

# 检查持久化
redis-cli LASTSAVE

# 检查键数量
redis-cli DBSIZE

# 检查慢查询
redis-cli SLOWLOG GET 10
```

#### Qdrant诊断

```bash
# 检查健康状态
curl http://localhost:6333/health

# 检查集合
curl http://localhost:6333/collections

# 检查集合详情
curl http://localhost:6333/collections/{collection_name}

# 检查集群状态
curl http://localhost:6333/cluster
```

#### Neo4j诊断

```bash
# 检查连接
cypher-shell -u neo4j -p password "RETURN 1"

# 检查数据库状态
cypher-shell "CALL dbms.diagnostics.listConfig()"

# 检查集群状态
cypher-shell "CALL dbms.cluster.overview()"

# 检查事务
cypher-shell "CALL dbms.listTransactions()"
```

### 3. 网络故障诊断

```bash
# 检查DNS解析
nslookup xagent-api.example.com
dig xagent-api.example.com

# 检查网络连接
ping -c 4 <target-host>
traceroute <target-host>

# 检查防火墙规则
aws ec2 describe-security-groups --group-ids sg-xxxxx

# 检查路由表
aws ec2 describe-route-tables --route-table-ids rtb-xxxxx

# 检查网络接口
aws ec2 describe-network-interfaces --network-interface-ids eni-xxxxx

# 检查VPN连接
aws ec2 describe-vpn-connections --vpn-connection-ids vpn-xxxxx
```

---

## 故障转移操作

### 1. 应用服务故障转移

#### 自动转移（推荐）

```bash
# 执行自动故障转移
./scripts/dr/failover.sh --auto

# 监控转移进度
./scripts/dr/monitor-failover.sh

# 验证转移完成
./scripts/dr/verify-failover.sh
```

#### 手动转移

```bash
# 步骤1：评估故障
./scripts/dr/assess-failure.sh

# 步骤2：停止故障实例
docker stop xagent-api

# 步骤3：更新负载均衡器
aws elbv2 deregister-targets \
  --target-group-arn arn:aws:elasticloadbalancing:... \
  --targets Id=i-xxxxx

# 步骤4：启动备用实例
docker start xagent-api-backup

# 步骤5：注册到负载均衡器
aws elbv2 register-targets \
  --target-group-arn arn:aws:elasticloadbalancing:... \
  --targets Id=i-yyyyy

# 步骤6：验证转移
./scripts/dr/verify-failover.sh
```

### 2. 数据库故障转移

#### PostgreSQL主从切换

```bash
# 步骤1：检查从库状态
psql -h standby-host -U xagent -d xagent_db -c "SELECT pg_last_wal_receive_lsn();"

# 步骤2：提升从库为主库
pg_ctl promote -D /var/lib/postgresql/data

# 或使用pg_basebackup
psql -h standby-host -U xagent -d xagent_db -c "SELECT pg_promote();"

# 步骤3：更新应用连接字符串
# 编辑 .env 文件或环境变量
export DATABASE_URL="postgresql://xagent:password@standby-host:5432/xagent_db"

# 步骤4：重启应用
docker restart xagent-api

# 步骤5：验证写入操作
psql -c "INSERT INTO test_table VALUES (1, 'test');"

# 步骤6：启动新的从库
pg_basebackup -h new-standby-host -D /var/lib/postgresql/data -U replication -v -P
```

#### Redis主从切换

```bash
# 步骤1：检查从库状态
redis-cli -h replica-host INFO replication

# 步骤2：提升从库为主库
redis-cli -h replica-host SLAVEOF NO ONE

# 步骤3：更新应用连接
export REDIS_URL="redis://replica-host:6379/0"

# 步骤4：重启应用
docker restart xagent-api

# 步骤5：验证写入操作
redis-cli SET test_key "test_value"

# 步骤6：配置新的从库
redis-cli -h new-replica-host SLAVEOF replica-host 6379
```

### 3. 跨区域故障转移

#### DNS切换

```bash
# 步骤1：检查备用区域状态
./scripts/dr/check-dr-region.sh

# 步骤2：更新Route53记录
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.xagent.com",
        "Type": "A",
        "TTL": 60,
        "ResourceRecords": [{"Value": "10.0.2.100"}]
      }
    }]
  }'

# 步骤3：等待DNS传播
sleep 120

# 步骤4：验证DNS解析
nslookup api.xagent.com

# 步骤5：验证流量转移
./scripts/dr/verify-traffic-shift.sh
```

#### 应用启动

```bash
# 步骤1：启动备用区域的所有服务
docker-compose -f docker-compose.dr.yml up -d

# 步骤2：等待服务就绪
./scripts/dr/wait-for-services.sh --region us-west

# 步骤3：验证服务健康
./scripts/dr/health-check.sh --region us-west

# 步骤4：执行功能测试
./scripts/dr/functional-test.sh --region us-west
```

#### 数据恢复

```bash
# 步骤1：从备份恢复数据
./scripts/dr/restore-from-backup.sh --backup-id latest --region us-west

# 步骤2：验证数据完整性
./scripts/dr/verify-data-integrity.sh

# 步骤3：启动数据同步
./scripts/dr/start-replication.sh --source us-east --target us-west

# 步骤4：监控同步进度
./scripts/dr/monitor-replication.sh
```

---

## 数据恢复操作

### 1. 从备份恢复

#### 完整恢复

```bash
# 步骤1：列出可用备份
./scripts/dr/list-backups.sh

# 步骤2：选择备份
BACKUP_ID="backup-2026-05-28-10-00-00"

# 步骤3：停止应用
docker stop xagent-api

# 步骤4：恢复数据库
./scripts/dr/restore-database.sh --backup-id $BACKUP_ID

# 步骤5：恢复缓存
./scripts/dr/restore-cache.sh --backup-id $BACKUP_ID

# 步骤6：恢复向量数据库
./scripts/dr/restore-qdrant.sh --backup-id $BACKUP_ID

# 步骤7：恢复图数据库
./scripts/dr/restore-neo4j.sh --backup-id $BACKUP_ID

# 步骤8：启动应用
docker start xagent-api

# 步骤9：验证恢复
./scripts/dr/verify-recovery.sh
```

#### 增量恢复

```bash
# 步骤1：恢复最后一个完整备份
./scripts/dr/restore-database.sh --backup-id backup-2026-05-28-00-00-00

# 步骤2：应用增量备份
./scripts/dr/apply-incremental-backup.sh --backup-id backup-2026-05-28-10-00-00

# 步骤3：应用差异备份
./scripts/dr/apply-differential-backup.sh --backup-id backup-2026-05-28-15-00-00

# 步骤4：验证恢复
./scripts/dr/verify-recovery.sh
```

### 2. 数据一致性修复

```bash
# 步骤1：检测数据不一致
./scripts/dr/detect-inconsistency.sh

# 步骤2：生成修复计划
./scripts/dr/generate-repair-plan.sh

# 步骤3：执行修复
./scripts/dr/execute-repair.sh --dry-run  # 先进行模拟运行

# 步骤4：验证修复
./scripts/dr/verify-repair.sh
```

### 3. 部分数据恢复

```bash
# 恢复特定表
./scripts/dr/restore-table.sh --table users --backup-id $BACKUP_ID

# 恢复特定时间范围的数据
./scripts/dr/restore-time-range.sh --start 2026-05-28T10:00:00 --end 2026-05-28T11:00:00

# 恢复特定用户的数据
./scripts/dr/restore-user-data.sh --user-id 12345 --backup-id $BACKUP_ID
```

---

## 验证与回切

### 1. 恢复验证

#### 数据完整性验证

```bash
# 验证表行数
./scripts/dr/verify-row-count.sh

# 验证关键字段
./scripts/dr/verify-critical-fields.sh

# 验证外键约束
./scripts/dr/verify-foreign-keys.sh

# 验证数据范围
./scripts/dr/verify-data-ranges.sh

# 生成验证报告
./scripts/dr/generate-verification-report.sh
```

#### 功能测试

```bash
# 测试API端点
./scripts/dr/test-api-endpoints.sh

# 测试用户认证
./scripts/dr/test-authentication.sh

# 测试数据查询
./scripts/dr/test-data-queries.sh

# 测试数据写入
./scripts/dr/test-data-writes.sh

# 执行完整功能测试
./scripts/dr/run-functional-tests.sh
```

#### 性能验证

```bash
# 测试响应时间
./scripts/dr/test-response-time.sh

# 测试吞吐量
./scripts/dr/test-throughput.sh

# 检查资源使用率
./scripts/dr/check-resource-usage.sh

# 检查复制延迟
./scripts/dr/check-replication-lag.sh

# 生成性能报告
./scripts/dr/generate-performance-report.sh
```

### 2. 回切流程

#### 准备回切

```bash
# 步骤1：检查主区域状态
./scripts/dr/check-primary-region.sh

# 步骤2：验证主区域就绪
./scripts/dr/verify-primary-ready.sh

# 步骤3：准备回切
./scripts/dr/prepare-failback.sh
```

#### 执行回切

```bash
# 步骤1：停止备用区域的写入
./scripts/dr/stop-dr-writes.sh

# 步骤2：同步最后的数据
./scripts/dr/sync-final-data.sh

# 步骤3：更新DNS指向主区域
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.xagent.com",
        "Type": "A",
        "TTL": 60,
        "ResourceRecords": [{"Value": "10.0.1.100"}]
      }
    }]
  }'

# 步骤4：等待DNS传播
sleep 120

# 步骤5：验证流量转移
./scripts/dr/verify-traffic-shift.sh

# 步骤6：停止备用区域服务
docker-compose -f docker-compose.dr.yml down
```

#### 验证回切

```bash
# 验证主区域接收流量
./scripts/dr/verify-primary-traffic.sh

# 验证数据一致性
./scripts/dr/verify-data-consistency.sh

# 验证性能指标
./scripts/dr/verify-performance-metrics.sh

# 生成回切报告
./scripts/dr/generate-failback-report.sh
```

---

## 常见问题

### Q1: 故障转移需要多长时间？

**A**: 取决于故障类型：
- 应用服务故障：5-10分钟
- 单个数据库节点故障：15-20分钟
- 整个数据中心故障：45-60分钟

### Q2: 会丢失多少数据？

**A**: 根据RPO目标：
- 关键业务数据：<5分钟
- 用户会话数据：<15分钟
- 向量数据库：<10分钟

### Q3: 如何验证故障转移成功？

**A**: 运行验证脚本：
```bash
./scripts/dr/verify-failover.sh
```

### Q4: 如何手动触发故障转移？

**A**: 使用手动转移命令：
```bash
./scripts/dr/failover.sh --manual --region us-west --force
```

### Q5: 故障转移失败怎么办？

**A**: 
1. 检查日志：`tail -f /var/log/xagent/disaster-recovery.log`
2. 联系DRP负责人
3. 执行手动恢复步骤

### Q6: 如何从备份恢复特定数据？

**A**: 使用部分恢复脚本：
```bash
./scripts/dr/restore-table.sh --table users --backup-id $BACKUP_ID
```

### Q7: 备份存储在哪里？

**A**: 备份存储在：
- 主区域：S3 + 本地存储
- 备用区域：S3 + 本地存储
- 跨区域复制：启用

### Q8: 如何测试灾难恢复计划？

**A**: 执行演练：
```bash
./scripts/dr/prepare-drill.sh --quarter Q1
./scripts/dr/inject-failure.sh --type app-crash
./scripts/dr/monitor-recovery.sh
./scripts/dr/verify-recovery.sh
./scripts/dr/generate-report.sh
```

---

**最后更新**: 2026-05-28  
**下次审查**: 2026-08-28
