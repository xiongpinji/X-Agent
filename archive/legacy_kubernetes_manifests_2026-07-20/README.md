# 归档说明: deployment/kubernetes/ 清单 (2026-07-20, Phase 2 Wave A / P1-15)

## 归档原因

仓库曾存在两套并行的 K8s 清单:

- `deployment/k8s/` —— namespace `xagent`, 标签 `app: xagent-api/worker/beat`,
  覆盖 api/worker/beat/postgres/redis/qdrant/neo4j/ingress/configmap/secret, 清单完整;
- `deployment/kubernetes/` —— namespace `production`, 标签 `app: xagent` + `component: api`,
  仅 api/service/ingress 三个文件, 且引用的 secret key (`database-url`、`secret-key` 等)
  与 `deployment/k8s/secret.yaml` 实际定义的 key 不一致。

两套并存导致"哪套是权威"无法判定(见 `commercial_audit/13_deployment_ops_audit.md` §3.2, P1-15)。

## 决策

保留 `deployment/k8s/` 为**唯一权威清单**, 本目录归档 `deployment/kubernetes/` 的全部 3 个文件。
`deployment/canary/canary-deployment.yaml` 已同步对齐到权威套约定(namespace xagent、
`app: xagent-api` + `version: canary` 标签、真实 secret key)。

## 权威路径

- 清单: `deployment/k8s/`
- Helm: `deployment/helm/` (CD 统一入口)
- 备份 CronJob: `deployment/k8s/backup-cronjob.yaml`

归档内容仅供历史参考, 禁止直接 `kubectl apply`。
