# P1-06: TLS 终结参考配置

> X-Agent API 本身以 HTTP 运行（容器/集群内部）；**TLS 必须在边界终结**。
> 本目录提供 nginx 与 Caddy 两份参考配置，供 compose/虚拟机/裸机部署直接使用；
> Kubernetes 部署请用 Helm ingress（`deployment/helm/values-production.yaml` 已含
> `tls: [{secretName: xagent-tls}]` + `ssl-redirect: "true"`，推荐 cert-manager 签发到该 secret）。

安全要点（两份配置均已落实）：

- 仅 TLS 1.2+，现代加密套件；HTTP 一律 301 跳 HTTPS。
- 后端组件（PostgreSQL/Redis/Qdrant/Neo4j）**绝不暴露公网**，仅反代 API 与前端。
- 透传 `X-Forwarded-For/Proto`——应用的限流（按 IP）与审计依赖真实客户端 IP。
- 探针 `/health`、`/ready` 走同一 vhost（kubelet/负载均衡器需要）。

## 文件

| 文件 | 用途 |
|---|---|
| `nginx.conf.example` | nginx 反向代理 + TLS 终结（证书路径按实际修改） |
| `Caddyfile.example` | Caddy 自动 HTTPS（Let's Encrypt 零配置签发） |
