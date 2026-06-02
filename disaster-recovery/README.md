# X-Agent 灾难恢复计划（DRP）- README

## 概述

X-Agent 灾难恢复计划（Disaster Recovery Plan, DRP）是一套完整的系统恢复方案，确保在发生重大故障时，系统能够快速恢复并最小化数据丢失。

**关键指标**:
- RTO（恢复时间目标）: <1小时
- RPO（恢复点目标）: <15分钟
- 故障转移自动化: >95%
- 服务可用性: 99.99%

---

## 目录结构

```
disaster-recovery/
├── DISASTER_RECOVERY_PLAN.md          # 灾难恢复计划（主文档）
├── DISASTER_RECOVERY_MANUAL.md        # 灾难恢复手册（操作指南）
├── DRILL_REPORT_TEMPLATE.md           # 演练报告模板
├── RCA_TEMPLATE.md                    # 故障根因分析模板
├── README.md                          # 本文件
├── config/
│   └── dr-config.env                  # 环境变量配置
├── scripts/
│   ├── health-check.sh                # 健康检查脚本
│   ├── failover.sh                    # 故障转移脚本
│   ├── verify-recovery.sh             # 恢复验证脚本
│   ├── monitor-replication.py         # 复制监控脚本
│   └── notify.py                      # 告警通知脚本
└── docker-compose.dr.yml              # 备用区域Docker配置
```

---

## 快速开始

### 1. 环境配置

```bash
# 复制配置文件
cp config/dr-config.env .env

# 编辑配置文件，设置实际的主机地址和凭证
vim .env

# 加载环境变量
source .env
```

### 2. 启动健康检查

```bash
# 一次性检查
./scripts/health-check.sh check

# 持续监控模式
./scripts/health-check.sh monitor
```

### 3. 执行故障转移

```bash
# 自动故障转移
./scripts/failover.sh --auto

# 手动故障转移
./scripts/failover.sh --manual --region us-west --force

# 模拟运行（不执行实际操作）
./scripts/failover.sh --auto --dry-run
```

### 4. 验证恢复

```bash
# 执行恢复验证
./scripts/verify-recovery.sh

# 查看验证报告
cat /var/log/xagent/recovery-verification-report.md
```

---

## 核心功能

### 1. 故障检测

**自动健康检查**:
- 应用层检查（HTTP健康端点）
- 数据库连接检查
- 缓存系统检查
- 基础设施检查（磁盘、内存、CPU）

**检查间隔**: 10秒  
**失败阈值**: 3次连续失败  
**告警延迟**: <1分钟

### 2. 自动故障转移

**转移流程**:
1. 检测主区域故障
2. 检查备用区域就绪
3. 停止主区域写入
4. 同步最后的数据
5. 更新DNS指向备用区域
6. 验证转移完成

**转移时间**: 15-45分钟（取决于故障类型）

### 3. 数据同步

**同步机制**:
- PostgreSQL: 流复制 + WAL日志
- Redis: 主从复制
- Qdrant: 快照 + 增量同步
- Neo4j: 事务日志 + 增量同步

**同步延迟**: <5分钟

### 4. 恢复验证

**验证项**:
- 应用可用性
- 数据库完整性
- 缓存完整性
- 数据一致性
- 功能测试
- 性能指标

**验证时间**: 10-15分钟

---

## 操作指南

### 应用服务故障

**症状**:
- API返回5xx错误
- 应用进程崩溃
- 无法连接到应用

**响应步骤**:
```bash
# 1. 检查应用状态
docker ps | grep xagent-api

# 2. 查看应用日志
docker logs xagent-api | tail -100

# 3. 重启应用
docker restart xagent-api

# 4. 如果重启失败，执行故障转移
./scripts/failover.sh --auto
```

### 数据库故障

**症状**:
- 数据库连接超时
- 查询响应缓慢
- 复制延迟过大

**响应步骤**:
```bash
# 1. 检查数据库状态
psql -h localhost -U xagent -d xagent_db -c "SELECT version();"

# 2. 检查复制状态
psql -c "SELECT * FROM pg_stat_replication;"

# 3. 如果主库故障，执行主从切换
./scripts/failover.sh --manual --region us-west --force
```

### 网络故障

**症状**:
- 应用无法连接到数据库
- 跨区域通信中断
- DNS解析失败

**响应步骤**:
```bash
# 1. 检查网络连接
ping <database-host>
nslookup <service-name>

# 2. 检查防火墙规则
aws ec2 describe-security-groups

# 3. 如果本地网络故障，转移到备用区域
./scripts/failover.sh --auto
```

### 数据中心故障

**症状**:
- 所有服务不可用
- 无法连接到任何资源
- 网络完全中断

**响应步骤**:
```bash
# 1. 确认主区域完全不可用
./scripts/health-check.sh check

# 2. 执行跨区域转移
./scripts/failover.sh --manual --region us-west --force

# 3. 验证备用区域服务正常
./scripts/verify-recovery.sh

# 4. 通知所有利益相关者
# 发送邮件、Slack消息等
```

---

## 演练计划

### 季度演练

**Q1演练** (3月):
- 类型: 应用服务故障转移
- 时间: 2小时
- 参与者: 应用团队、运维团队

**Q2演练** (6月):
- 类型: 数据库故障转移
- 时间: 3小时
- 参与者: DBA、运维团队

**Q3演练** (9月):
- 类型: 跨区域转移
- 时间: 4小时
- 参与者: 所有团队

**Q4演练** (12月):
- 类型: 完整灾难恢复
- 时间: 6小时
- 参与者: 所有团队、管理层

### 执行演练

```bash
# 1. 准备演练环境
./scripts/prepare-drill.sh --quarter Q1

# 2. 注入故障
./scripts/inject-failure.sh --type app-crash --region us-east

# 3. 监控恢复过程
./scripts/monitor-recovery.sh

# 4. 验证恢复
./scripts/verify-recovery.sh

# 5. 收集指标
./scripts/collect-metrics.sh

# 6. 生成报告
./scripts/generate-report.sh --output drill-report-q1.md

# 7. 清理环境
./scripts/cleanup-drill.sh
```

---

## 监控与告警

### 关键指标

**应用层**:
- 请求延迟 (p50, p95, p99)
- 错误率
- 吞吐量
- 活跃连接数

**数据库层**:
- 查询延迟
- 复制延迟
- 磁盘使用率
- 连接数

**基础设施**:
- CPU使用率
- 内存使用率
- 磁盘I/O
- 网络带宽

### 告警规则

**P1告警** (立即响应):
- 应用不可用
- 数据库不可用
- 数据丢失检测

**P2告警** (5分钟内响应):
- 复制延迟 >5分钟
- 磁盘使用率 >90%
- 错误率 >1%

**P3告警** (15分钟内响应):
- 响应时间 >1秒
- CPU使用率 >80%
- 内存使用率 >85%

### 告警通知

**通知渠道**:
- 邮件 (所有告警)
- Slack (P1/P2告警)
- 短信 (P1告警)
- 电话 (P1告警 + 无响应)

---

## 常见问题

### Q1: 故障转移需要多长时间？

**A**: 取决于故障类型：
- 应用服务故障: 5-10分钟
- 单个数据库节点故障: 15-20分钟
- 整个数据中心故障: 45-60分钟

### Q2: 会丢失多少数据？

**A**: 根据RPO目标：
- 关键业务数据: <5分钟
- 用户会话数据: <15分钟
- 向量数据库: <10分钟

### Q3: 如何验证故障转移成功？

**A**: 运行验证脚本：
```bash
./scripts/verify-recovery.sh
```

### Q4: 如何手动触发故障转移？

**A**: 使用手动转移命令：
```bash
./scripts/failover.sh --manual --region us-west --force
```

### Q5: 故障转移失败怎么办？

**A**: 
1. 检查日志: `tail -f /var/log/xagent/disaster-recovery.log`
2. 联系DRP负责人
3. 执行手动恢复步骤

### Q6: 如何从备份恢复特定数据？

**A**: 使用部分恢复脚本：
```bash
./scripts/restore-table.sh --table users --backup-id $BACKUP_ID
```

### Q7: 备份存储在哪里？

**A**: 备份存储在：
- 主区域: S3 + 本地存储
- 备用区域: S3 + 本地存储
- 跨区域复制: 启用

### Q8: 如何测试灾难恢复计划？

**A**: 执行演练：
```bash
./scripts/prepare-drill.sh --quarter Q1
./scripts/inject-failure.sh --type app-crash
./scripts/monitor-recovery.sh
./scripts/verify-recovery.sh
./scripts/generate-report.sh
```

---

## 联系方式

### 灾难恢复团队

| 角色 | 姓名 | 电话 | 邮箱 |
|------|------|------|------|
| DRP负责人 | 张三 | 13800138000 | zhangsan@xagent.com |
| 基础设施主管 | 李四 | 13800138001 | lisi@xagent.com |
| 数据库管理员 | 王五 | 13800138002 | wangwu@xagent.com |
| 应用架构师 | 赵六 | 13800138003 | zhaoliu@xagent.com |

### 升级流程

1. **T+0分钟**: 故障检测，通知值班工程师
2. **T+5分钟**: 初步评估，确定故障级别
3. **T+10分钟**: 激活灾难恢复团队
4. **T+15分钟**: 执行故障转移
5. **T+30分钟**: 恢复验证
6. **T+60分钟**: 根因分析

---

## 相关文档

- [灾难恢复计划](DISASTER_RECOVERY_PLAN.md) - 完整的DRP文档
- [灾难恢复手册](DISASTER_RECOVERY_MANUAL.md) - 操作指南
- [演练报告模板](DRILL_REPORT_TEMPLATE.md) - 演练报告示例
- [故障根因分析模板](RCA_TEMPLATE.md) - RCA示例

---

## 版本历史

| 版本 | 日期 | 作者 | 变更 |
|------|------|------|------|
| 1.0 | 2026-05-28 | 张三 | 初始版本 |

---

## 许可证

X-Agent 灾难恢复计划采用 MIT 许可证。

---

**最后更新**: 2026-05-28  
**下次审查**: 2026-08-28  
**审查周期**: 每季度一次
