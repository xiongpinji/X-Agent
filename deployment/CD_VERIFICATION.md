# X-Agent CD 跑通证据定义 (P1-15)

**日期**: 2026-07-26
**范围**: `.github/workflows/deploy.yml` 的 staging 部署链路 + `deployment/helm/` chart

## 背景与诚实声明

本机与 CI 当前均**无真实 k8s 集群**。因此"CD 跑通"按可验证程度分级定义,
每级都有明确的、可复查的证据物。不允许把低级别证据表述为"已部署上线"。

## 证据分级

| 级别 | 名称 | 验证内容 | 证据物 | 当前状态 |
|------|------|---------|--------|---------|
| L1 | Chart 可渲染 | `helm lint` + `helm template` 对 default / values-production / values-multiregion 三套 values 全部通过, 渲染产物 YAML 可解析 | CI 日志; 本地存档 `commercial_audit/evidence/helm-template-*-2026-07-26.yaml` (各 22 个 manifest, 10 种 kind) | ✅ 2026-07-26 已验证 (helm v3.14.4) |
| L2 | 服务端 dry-run | `helm upgrade --install --dry-run --debug` 指向真实集群, API server 接受全部 manifest(schema/准入校验通过) | CI job "Deploy to staging" 日志中含 helm debug 输出与 `NAME: xagent` 的 release 记录 | ⬜ 阻塞: 需配置 `STAGING_KUBECONFIG` secret + 真实集群 |
| L3 | 真实部署 + 冒烟 | `helm upgrade --install`(非 dry-run) 后 `kubectl rollout status` 全绿, 且 `curl $STAGING_SMOKE_URL/health` 返回 200 | CI 日志 + rollout 状态 + 冒烟 200 截图/日志 | ⬜ 阻塞: 同 L2, 另需 `STAGING_SMOKE_URL` |

## deploy.yml staging 现状 (2026-07-26 改造后)

- **每次必跑 (L1)**: `Validate Helm chart` 步骤真实执行 `helm lint` ×2 +
  `helm template` ×2, 任一失败即阻断流水线(无 `continue-on-error`)。
- **条件触发 (L2)**: 配置 GitHub secret `STAGING_KUBECONFIG` 后, `Deploy to staging`
  步骤自动转为真实 `helm upgrade --install --dry-run --debug`; 未配置时打印
  前置条件清单并以 notice 显式标记 TODO(P1-15)。
- **条件触发 (L3 冒烟)**: 配置 `STAGING_SMOKE_URL` 后 smoke test 步骤转为真实
  `curl -fsS $STAGING_SMOKE_URL/health`。

## L2/L3 前置条件清单

1. 预置 staging 命名空间的 k8s 集群(EKS/GKE/自建均可), 已安装 ingress-nginx;
2. 将该集群 kubeconfig 写入 GitHub secret `STAGING_KUBECONFIG`;
3. 配置 `AWS_ROLE_TO_ASSUME_STAGING`(如需访问基础设施);
4. 在 GitHub Environment `staging` 中配置保护规则;
5. 集群可拉取 ghcr.io 镜像(必要时配置 imagePullSecret);
6. (L3) 配置 `STAGING_SMOKE_URL` 指向 staging API 根地址。

## 本地复现 L1 的命令

```bash
helm lint deployment/helm
helm template xagent deployment/helm
helm template xagent deployment/helm -f deployment/helm/values-production.yaml
helm template xagent deployment/helm -f deployment/helm/values-multiregion.yaml
```

> 注: 2026-07-26 首次验证时发现并修复了 `_helpers.tpl` 的缺陷——默认
> `neo4j.enabled=false` 且 `appEnv.neo4jEnabled=false` 时, `xagent.neo4jHost`
> 强制要求 `external.neo4jHost` 导致三套 values 全部渲染失败。修复后仅当
> neo4j 功能真实启用时才强制外部端点。
