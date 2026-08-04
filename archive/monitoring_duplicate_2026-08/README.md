# 归档说明：重复监控栈（2026-08-04）

> P0-04 收尾：监控链四套 prometheus.yml 收敛为一套。

## 归档内容

- `docker-compose.monitoring.yml`（87 行简版，`prom/prometheus:latest` 未锁版本，无 recording_rules 挂载）
- `prometheus/prometheus.yml` + `prometheus/alerts.yml`（test 标签的旧配置）

## 权威实现（保留）

`monitoring/` 目录是唯一权威监控栈：

- `monitoring/docker-compose.monitoring.yml`（323 行完整版，`prom/prometheus:v2.48.0` 锁版本）
- `monitoring/prometheus.yml`（rule_files 引用 `alert_rules.yml` + `recording_rules.yml`）
- `monitoring/docker-compose.monitoring.yml` 已挂载 recording_rules.yml
- Makefile 监控目标（line 363+）全部指向本栈

## 归档原因

两套栈并存违反 P0-04「收敛为一套」要求；deployment/ 简版缺 recording_rules
挂载，按其启动会得到规则缺失的半成品监控。应用侧监控链（MetricsMiddleware
+ /metrics 挂载，main.py）与此归档无关，保持不动。

## 同步更新

- `scripts/test-env-checklist.sh`：检查项改指 `monitoring/prometheus.yml` / `alert_rules.yml` / `recording_rules.yml`
- `scripts/deploy-test-env.sh`：移除 `deployment/prometheus`、`deployment/migrations`（P0-01 旧路径）两个过期 mkdir
- 文档 `deployment/MONITORING_QUICKSTART.md`、`docs/operations/monitoring/MONITORING.md` 路径引用改指 monitoring/
