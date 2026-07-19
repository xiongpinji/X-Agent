# X-Agent 部署与运维商用就绪度审计报告

- **角色标签**: 部署运维审计员
- **审计日期**: 2026-07-19
- **任务范围**: docker-compose 系列文件与 Dockerfile、`deployment/`(k8s/helm/canary/backup/rollback)、`monitoring/`(Prometheus/Grafana/Alertmanager)、`DISASTER_RECOVERY.md` 与 `disaster-recovery/`、性能与并发基准(`benchmarks/`、`PERFORMANCE_BENCHMARK_REPORT.md`、`locustfile.py`)、`cloud/` 云版本架构、水平扩展能力(Celery/Redis)、健康检查与优雅停机
- **审计方法**: 逐文件实读配置与代码，区分"配置存在"与"经验证可用"；所有结论附 路径:行号 证据
- **总体评分**: **2.0 / 10(不可商用交付)** —— 表面资产齐全(4 套 Compose、2 套 K8s 清单、Helm Chart、监控栈、DR 文档体系),但经代码级核对，多条关键链路在真实环境中会立即失败，且性能基准报告为占位/样例数据，无任何"已验证"证据。

---

## 一、审计结论总览:「配置存在」 vs 「验证可用」对照表

| 能力项 | 配置/文件存在 | 经审计可用 | 关键证据 |
|---|---|---|---|
| Dockerfile(多阶段/非 root/健康检查) | ✅ | ⚠️ 基本可用 | `Dockerfile:3-70` |
| docker-compose 主栈 | ✅ | ❌ 全新部署会失败 | `docker-compose.yml:17` 引用不存在的 init.sql |
| Celery worker/beat(异步任务层) | ✅(配置) | ❌ 必然启动失败 | 全后端无 Celery app，见 §五 |
| K8s 清单(deployment/k8s) | ✅ | ❌ 环境变量前缀错误，Pod 以 sqlite 默认配置启动 | `deployment/k8s/xagent-api-deployment.yaml:70-100` |
| K8s 清单(deployment/kubernetes) | ✅ | ❌ 同上，且与 k8s/ 双轨不一致 | `deployment/kubernetes/deployment.yaml:48-60` |
| Helm Chart | ✅ | ❌ 仅 5 个模板，worker/beat/数据库等无模板 | `deployment/helm/templates/` |
| 金丝雀发布 | ✅ | ❌ 依赖的监控指标从未产生 | `deployment/canary/deploy-canary.sh:80` |
| Prometheus 监控 | ✅(4 份配置) | ❌ 抓取路径与后端实际暴露不匹配 | §六 |
| Grafana 看板 | ✅ | ⚠️ 存在但数据源无真实指标可显示 | `monitoring/grafana-dashboard*.json` |
| 告警(Alertmanager/规则) | ✅ | ❌ 告警表达式引用的指标不存在 | `monitoring/alert_rules.yml:7` |
| 备份脚本 | ✅ | ⚠️ PG/Redis 可用；Qdrant 备份 API 写错 | `deployment/backup/backup.sh:94` |
| 回滚脚本 | ✅ | ⚠️ 逻辑合理但未编排验证；依赖的 deployment 命名与清单不一致 | `deployment/rollback.sh:9-12` |
| 灾难恢复文档体系 | ✅ | ❌ 引用的 runbook/脚本路径不存在；无演练记录 | `DISASTER_RECOVERY.md:240,399-407` |
| 性能基准报告 | ✅ | ❌ 根目录版全为占位符；benchmarks/ 版为硬编码样例数据 | §七 |
| Locust 压测脚本 | ✅ | ⚠️ 脚本真实可运行，无执行结果留存 | `locustfile.py:1-203` |
| 云版本架构(cloud/) | ✅(文档+2 个服务文件) | ❌ 未被后端引用，未集成 | §八 |
| 水平扩展(HPA) | ✅ | ❌ 默认 sqlite/文件存储使多副本失效 | §九 |
| 健康检查端点 | ✅ | ✅ 代码真实实现 | `backend/app/main.py:665,689` |
| 优雅停机 | ✅(部分) | ⚠️ 应用层有 shutdown 钩子；K8s 层缺 preStop/宽限期 | §十 |
| CI/CD | ✅(13 个 workflow) | ❌ CD 流程引用了 Helm 中不存在的 deployment | `.github/workflows/deploy-production.yml:166` |

---

## 二、Dockerfile 与 docker-compose 系列

### 2.1 Dockerfile —— 基本合格(少量瑕疵)

- 多阶段构建(builder + runtime),`Dockerfile:3`、`Dockerfile:28`;
- 非 root 运行:`Dockerfile:57-60` 创建 uid 1000 的 `xagent` 用户并 `USER xagent`;
- 内置 HEALTHCHECK 打 `/health`:`Dockerfile:63-64`,后端确有该端点(`backend/app/main.py:665-673`),✅ 匹配;
- 锁定依赖:`Dockerfile:15` 使用 `requirements-lock.txt`,✅;
- **瑕疵 1**: 同一镜像同时用于 API 与 worker/beat(`docker-compose.yml:184-240`),worker 容器不监听 8000 端口，镜像级 HEALTHCHECK 在 worker 上必然失败(compose 未为 worker 覆盖 healthcheck);
- **瑕疵 2**: 运行时镜像未安装 Playwright 浏览器依赖，而配置项存在 `XAGENT_PLAYWRIGHT_HEADLESS`(`docker-compose.yml:140`),浏览器自动化能力在容器内不可用(待验证，但镜像中无相关安装步骤，见 `Dockerfile:33-39`)。

### 2.2 docker-compose.yml(主栈)—— 存在致命引用错误

- **致命问题**: `docker-compose.yml:17` 挂载 `./deployment/migrations/init.sql:/docker-entrypoint-initdb.d/01-init.sql`,但 `deployment/migrations/` 目录下**只有 `migrate.py`，不存在 init.sql**(实测 `ls deployment/migrations/`)。Docker 会将不存在的主机路径创建为**空目录**挂载，postgres 初始化脚本不会执行；在部分 Docker 版本上直接报错。即**全新环境 `docker compose up` 无法得到可用的数据库 Schema**。
- 环境变量前缀处理正确:API/worker/beat 注入 `XAGENT_*` 变量(`docker-compose.yml:116-148`),与 `backend/app/settings.py:14` 的 `env_prefix="XAGENT_"` 匹配，✅;
- 默认 LLM 为 mock:`docker-compose.yml:123` `XAGENT_LLM_BACKEND:-mock`,与 `DEPLOYMENT.md:20` 的开发定位一致；
- 默认密码硬编码回退值:`docker-compose.yml:10` `xagent_secure_password` 等，商用必须强制覆盖；
- 开发式 bind mount `./backend:/app/backend`(`docker-compose.yml:167`)出现在主 compose 中，生产使用会覆盖镜像内代码，属危险默认值;
- `docker-compose.postgres.yml:12` 引用 `./backend/migrations/init_schema.sql`,该文件**存在**(`backend/migrations/init_schema.sql`),✅ —— 说明主 compose 的 init.sql 引用应为笔误/遗漏，但至今未修。

### 2.3 docker-compose.performance.yml —— 环境变量前缀错误

- `docker-compose.performance.yml:46-48` 注入 `DATABASE_URL`/`REDIS_URL`(**无 XAGENT_ 前缀**)。后端 Settings 只读 `XAGENT_` 前缀(`backend/app/settings.py:14`,字段 `database_url` 见 `settings.py:33`,无 alias),因此该性能栈的 API 实际仍以 sqlite 默认配置启动，**性能测量环境与被测目标不一致**。`DEPLOYMENT.md:7` 明确写了前缀规则，此文件与之矛盾。

---

## 三、deployment/(k8s / helm / canary / backup / rollback)

### 3.1 deployment/k8s/(主清单)—— 结构漂亮，接通即坏

**做得好的部分(配置存在)**:
- API 3 副本 + RollingUpdate(maxUnavailable=0)+ podAntiAffinity:`deployment/k8s/xagent-api-deployment.yaml:10-36`;
- 资源 requests/limits:`:117-123`;
- securityContext(runAsNonRoot/readOnlyRootFilesystem/drop ALL):`:140-147`;
- HPA(cpu 70%/mem 80%, 3-10 副本，带 scaleUp/scaleDown behavior):`:176-217`;
- postgres/redis/qdrant/neo4j/worker/beat 均有独立清单文件。

**致命问题(经验证不可用)**:
1. **环境变量前缀全线错误**:清单注入 `DATABASE_URL`(`xagent-api-deployment.yaml:70`)、`REDIS_URL`(`:87`)、`QDRANT_URL`(`:94`)、`NEO4J_URI`(`:101`),均无 `XAGENT_` 前缀。后端 Settings 不会读取它们(`backend/app/settings.py:14,33,41,45`),Pod 将以默认 `sqlite:///./data/xagent.db` 启动;
2. **与 readOnlyRootFilesystem 冲突**:sqlite 默认路径需写 `/app/data`,而 `:144` 设置 `readOnlyRootFilesystem: true` 且未挂载 /app/data 卷(`:148-157` 只挂 /tmp 与 /app/logs)→ **API Pod 写库即失败**;
3. **readinessProbe 用错端点**:`:132-139` readiness 与 liveness 都打 `/health`;后端专门实现了深度就绪探针 `/ready`(`backend/app/main.py:689-744`),却从未被任何清单使用;
4. 镜像 `xagent:latest` + `imagePullPolicy: Always`(`:39-40`),无 registry、无版本锚定，不可复现;
5. **Celery 命令必败**:`deployment/k8s/xagent-worker-deployment.yaml:39-45` 与 `xagent-beat-deployment.yaml:22-23` 均执行 `celery -A backend.app.workflow_worker ...`,而该模块不是 Celery 应用(详见 §五),worker/beat 会 CrashLoopBackOff;
6. 无 `terminationGracePeriodSeconds`、无 preStop(全仓仅 `deployment/kubernetes/deployment.yaml:138` 设置了 30s 宽限期)。

### 3.2 deployment/kubernetes/(第二套清单)—— 双轨重复且同样错误

- 与 `deployment/k8s/` 并存的第二套清单(`deployment/kubernetes/deployment.yaml` 等 3 个文件),命名空间用 `production`(`:5`),标签用 `app: xagent`(`:7-8`),与 k8s/ 套的 `namespace: xagent`、`app: xagent-api` 不一致;
- 同样注入无前缀 `DATABASE_URL`/`REDIS_URL`/`QDRANT_URL`(`:48-67`);
- 唯一亮点:`:138` 设置了 `terminationGracePeriodSeconds: 30`;
- `deployment/canary/deploy-canary.sh:9` 默认 `NAMESPACE=production`、`deployment/rollback.sh:9-12` 引用 `xagent-api/xagent-worker/xagent-beat` —— 脚本族对接的是这一套，而 `deployment/k8s/` 那套(namespace xagent)与脚本不兼容。**两套清单并存、谁也说不清哪套是权威**。

### 3.3 deployment/helm/ —— Chart 严重不完整

- 模板仅 5 个:`api-deployment.yaml`、`configmap.yaml`、`ingress.yaml`、`namespace.yaml`、`secret.yaml`;
- 而 `values.yaml` 声明了 `worker:`(`:38-54`)、`beat:`(`:57-66`)、`postgres:`(`:69-80`)、`redis:`(`:83-94`)、`qdrant:`(`:97-108`)、`neo4j:`(`:111-122`)、`backup:`(`:184-187`)—— **这些组件没有任何对应模板,`helm install` 只会部署一个 API Deployment**;
- **values.yaml 存在重复键**:`redis` 出现两次(`:83` 与 `:161`)、`qdrant` 两次(`:97` 与 `:165`)、`neo4j` 两次(`:111` 与 `:168`)。YAML 后值覆盖前值，第一次定义的 image/storage/resources 被静默丢弃;
- ConfigMap 键全部无前缀(`deployment/helm/templates/configmap.yaml:7-19`),且**根本没有 DATABASE_URL**;Secret 同样无前缀。即使模板补齐，应用仍读不到配置;
- readiness 同样打 `/health`(`templates/api-deployment.yaml:60-67`);
- 明文默认口令:`values.yaml:149-153` `change-me-in-production`;
- **CD 断链**:`.github/workflows/deploy-production.yml:151-166` 先 `helm upgrade --install`,随后 `kubectl rollout status deployment/xagent-worker` —— Chart 里不存在 worker Deployment,该步骤必然超时失败。即 **CD 流水线从未被真正跑通过**。

### 3.4 金丝雀(deployment/canary/)—— 框架像样，判据失效

- `deploy-canary.sh` 实现了分阶段副本扩量(1→2→3→5→10,`:11`)、错误率阈值自动回滚(`:92-97`,`:119-124`)、最终全量晋升(`:136-162`),脚本逻辑完整;
- **但判据指标不存在**:脚本查询 `http_requests_total{version='canary',status=~'5..'}`(`:80`)与 `http_request_duration_seconds_bucket{version='canary'}`(`:127`)。后端**没有任何在运行的代码产生这两个指标**(详见 §六:PrometheusMiddleware 未挂载);Prometheus 查询恒为空→错误率恒为 0→**金丝雀分析形同虚设，任何版本都会"通过"**;
- 流量分配靠副本数比例，无 Argo Rollouts/Flagger/服务网格权重路由，且 canary 与 stable 的 Service selector 未在仓库中给出对应分流配置(`canary-deployment.yaml` 只定义 Deployment);
- `canary-deployment.yaml:48-67` 同样是无前缀环境变量问题。

### 3.5 备份与回滚

**备份**:
- `deployment/backup/backup.sh` 是质量较好的脚本:pg_dump custom 格式(`:62-69`)、Redis RDB(`:85`)、manifest 生成(`:113-140`)、S3 可选上传(`:147-161`)、保留期清理(`:165`)、Slack 通知(`:175-190`);
- **Qdrant 备份 API 写错**:`:94` 调用 `POST /collections/backup`。Qdrant 官方备份机制是快照 API(`POST /collections/{collection_name}/snapshots`)或全量存储快照(来源:[Qdrant 官方 Backup and Restore 文档](https://qdrant-qdrant-18.mintlify.app/operations/backup-restore),2026-03-04 访问;另见 [ComputingForGeeks: Backup and Restore Qdrant Snapshots](https://computingforgeeks.com/qdrant-backup-snapshot-restore/),2026-05-31)。`/collections/backup` 端点不存在，该步骤会静默走到 `:99` 的 warn 分支,**给人"已备份"的错觉**;
- 无定时化:k8s/helm 中无 Backup CronJob(values.yaml:184-187 声明了 backup 段但无模板);
- 另有 `deployment/scripts/backup-database.sh`、`monitoring/scripts/backup.sh` 等多份重叠脚本，未收敛。

**回滚**:
- `deployment/rollback.sh`(232 行)支持版本指定/带库回滚/健康检查重试，结构合理;
- 但依赖 `xagent-api/xagent-worker/xagent-beat` 三个 deployment(`:10-12`),与 Helm Chart(只有 api)和 k8s/ 套清单(namespace 不同)均不完全匹配;
- `ROLLBACK_PROCEDURE.md:13-18` 宣称"CI/CD 自动回滚",CD 本身未跑通(见 3.3),该宣称无支撑;
- `deployment/migrations/migrate.py` 的 restore/verify 子命令真实存在(`:260-264`、`:250-252`),是少数代码与文档一致的点。

---

## 四、灾难恢复(DISASTER_RECOVERY.md 与 disaster-recovery/)

### 4.1 文档体系(存在性 ✅)

- `DISASTER_RECOVERY.md`(423 行):RTO/RPO 表(`:9-16`)、6 类场景处置、备份策略、告警路由、演练计划、通讯分级，结构完整;
- `disaster-recovery/` 含操作手册、计划、RCA 模板、演练报告模板及 3 个脚本(`failover.sh` 409 行、`health-check.sh`、`verify-recovery.sh` 421 行),脚本有真实内容。

### 4.2 经验证的问题

1. **引用路径不存在**:`DISASTER_RECOVERY.md:399-407` 列出 `/deployment/runbooks/` 下 6 本 runbook,实测 `deployment/runbooks/` **不存在**;`:240` 引用 `deployment/health-check.sh`,也不存在(真实文件在 `disaster-recovery/scripts/health-check.sh`);
2. **Qdrant 恢复 API 同样错误**:`:178`、`:226`、`:292` 使用 `POST /collections/restore`,与官方快照恢复 API 不符(来源同 §3.5);
3. **无任何演练证据**:全仓只有 `disaster-recovery/DRILL_REPORT_TEMPLATE.md`(模板),没有任何一次实际演练报告;`disaster-recovery/IMPLEMENTATION_SUMMARY.md:13` 宣称"达到 99.99% 的可用性目标"——在四个月内无演练、无监控数据的情况下，该宣称**不可信**;
4. RTO/RPO 指标(`DISASTER_RECOVERY.md:9-16`)没有测量来源，属目标值而非验证值。

---

## 五、水平扩展能力(Celery/Redis)—— 本审计最严重的发现

### 5.1 Celery 任务层完全未实现(配置存在 ✅ / 可用 ❌)

- `docker-compose.yml:189`(worker)、`:240`(beat)、`deployment/k8s/xagent-worker-deployment.yaml:39-45`、`xagent-beat-deployment.yaml:22-23`、`deploy-canary.sh:147-153` 全部假定存在 Celery 应用 `backend.app.workflow_worker`;
- 实测:`backend/app/workflow_worker.py`(84 行)是一个 **asyncio 轮询脚本**(`:31-35` `run_forever` 循环),全文无 celery 导入;对 `backend/` 全目录 grep `from celery|import celery|Celery\(` **零命中**;
- `requirements.txt:44` 声明 `celery==5.3.0`,但无任何代码使用;
- **结论**: 所有编排中的 worker/beat 容器启动即崩溃;"Celery + Redis 分布式任务队列"这一水平扩展叙事在代码中不存在。实际可用的异步机制是单进程 asyncio 轮询(`workflow_worker.py:31-35`),无法多副本竞争消费(无 broker 去重/确认机制，多实例会重复触发同一 schedule,`run_due` 的 lease 机制见 `:22-26`,其并发安全性未经测试证据支持)。

### 5.2 多副本状态一致性

- 默认存储全部是**本地文件**:memory/traces/runs/workflows/approvals/api_keys/audit 等 jsonl 路径(`backend/app/settings.py:34,48-55`),默认库为 sqlite(`:33`)。在 3 副本 Deployment 下，每个 Pod 各有独立状态 → 数据分裂;
- Redis 仅用于部分会话(auth):`backend/app/api/auth.py:69-70` 在 `settings.redis_url` 存在时启用 Redis 客户端,✅ 有正确方向，但覆盖面小;
- HPA 配置存在(`deployment/k8s/xagent-api-deployment.yaml:176-217`),但**无状态化前提未达成**,HPA 一旦生效即造成数据不一致;
- WebSocket 多端同步所需的分片/粘性会话未见任何 ingress 级配置(待验证,helm ingress 模板仅基础注解)。

---

## 六、监控(monitoring/ + deployment/prometheus|grafana|alertmanager)

### 6.1 指标暴露端：后端真实能力

- 唯一随主应用挂载的指标端点是 `/api/v1/metrics/prometheus`(`backend/app/main.py:515` → `backend/app/api/metrics.py:57-83`),仅输出 `xagent_runs_total` 等 12 个**业务计数 gauge**;
- 完整的 HTTP 指标中间件存在但未接线:`backend/app/services/observability/prometheus_middleware.py:22-100` 定义了 `PrometheusMiddleware` 与 `metrics_endpoint`;`backend/app/monitoring/__init__.py:63-68` 也提供 `/metrics` 挂载逻辑——但 `initialize_monitoring` **在 main.py 中从未被调用**(grep `initialize_monitoring|monitoring` 于 main.py 零命中),main.py 实际挂载的中间件只有 CORS/CSRF/限流/日志/租户/安全头(`main.py:351-440`);
- 另一套指标定义 `backend/app/core/metrics.py:53-60` 使用 `xagent_http_requests_total` 命名，同样未暴露。

### 6.2 Prometheus 配置：四套互相矛盾，三套必坏

| 配置文件 | 抓取路径 | 与后端匹配? |
|---|---|---|
| `monitoring/prometheus.yml:43` | `/metrics` | ❌ 端点未挂载 |
| `monitoring/prometheus/prometheus.yml:26` | `/api/v1/metrics/prometheus` | ✅ 唯一正确 |
| `deployment/prometheus/prometheus.yml:27,35` | `/metrics` + `/health` | ❌ `/health` 返回 JSON,非指标格式 |
| 根目录 `prometheus.yml:18` | `/metrics` | ❌ |

- `monitoring/docker-compose.yml:10-11` 挂载 `monitoring/prometheus.yml` + `alert_rules.yml`,但该 prometheus.yml 的 `rule_files` 还要求 `recording_rules.yml`(`monitoring/prometheus.yml:31-33`),**未挂载 → Prometheus 启动即失败**;
- `monitoring/prometheus.yml:39` 抓取目标写 `localhost:8000` —— 在 Prometheus 容器内指向自身，永远抓不到 API;
- `monitoring/prometheus.yml:10-19` 配置 remote_write 到不存在的 `prometheus-remote-storage:9009`,`:26-29` 引用未部署的 Consul,启动后持续报错。

### 6.3 告警链：表达式引用的指标不存在

- `monitoring/alert_rules.yml:7,17,30,41` 等使用 `xagent:api:latency:p95:5m`、`xagent:api:error_rate:5m` 等 recording 指标，来自 `monitoring/recording_rules.yml:6-19`,其原始指标为 `xagent_api_requests_total`、`xagent_api_request_duration_seconds_bucket` —— **这些指标没有任何在运行的代码产生**(中间件未接线)。整个告警链从数据源断掉;
- 告警 runbook 链接为占位符:`alert_rules.yml:15` `https://wiki.example.com/runbooks/...`;
- Alertmanager 配置存在(`deployment/alertmanager/alertmanager.yml`、`monitoring/alertmanager.yml`、`monitoring/alertmanager/config.yml` 三份),接收器真实性待验证。

### 6.4 Grafana

- 看板 JSON 充足(`deployment/grafana/dashboards/` 5 个、`monitoring/grafana-dashboard-*.json` 5 个)、provisioning 齐备(`deployment/grafana/provisioning/datasources.yml`),`monitoring/docker-compose.yml:28` 管理员密码硬编码 `admin`;
- 看板面板引用的指标大多来自不存在的 HTTP 指标流，**看板会渲染为空**。

### 6.5 冗余与收敛

存在 monitoring/、deployment/{prometheus,grafana,alertmanager}、根 prometheus.yml 共 **3+ 套监控定义**,`deployment/MONITORING_QUICKSTART.md` 与 `monitoring/README.md` 各说一套，未收敛权威路径。

---

## 七、性能与并发基准 —— 无任何可信实测数据

1. **根目录 `PERFORMANCE_BENCHMARK_REPORT.md`(655 行)是未执行的模板**:全部指标为 `-` 占位符(`:24-32`、`:52-61` 等),测试日期写 2026-05-26 但无一个数字;
2. **`benchmarks/PERFORMANCE_BENCHMARK_REPORT.md` 是样例生成物**:数据来自 `benchmarks/report_generator.py:524-556` 的 `main()` —— 函数名即 "Generate sample reports",硬编码 `total_time: 0.10` 等假数据。报告中的 "V2 vs V1 +36.4%" 等对比(`benchmarks/PERFORMANCE_BENCHMARK_REPORT.md:40-46`)**不是实测**;
3. 可运行的压测资产真实存在:`locustfile.py`(203 行，登录+多任务权重,`:14-60`)、`benchmark_concurrency.py`、`database_benchmark.py`、`performance_tests.py`、`benchmarks/run_benchmarks.py` —— 但仓库中**没有任何一次执行的结果文件**;
4. `docker-compose.performance.yml` 因环境变量前缀错误(见 §2.3),即使跑了也测的是 sqlite 配置;
5. `CONCURRENCY_ARCHITECTURE.md`/`CONCURRENCY_IMPLEMENTATION_REPORT.md` 为设计文档，无基准数据支撑。

---

## 八、cloud/ 云版本架构 —— 设计与代码脱节

- 文档体系完整(8 份 md):`cloud/CLOUD_ARCHITECTURE.md`(611 行，宣称 WebSocket 实时同步、CRDT 冲突解决、端到端加密、离线支持，`:56-63`)、`DEPLOYMENT_GUIDE.md`(含 `terminationGracePeriodSeconds: 30` 示例,`:837`)、`DATABASE_SCHEMA.md`、`OPENAPI_SPEC.md` 等;
- 代码仅 `sync_service.py`(553 行)与 `encryption_service.py`(556 行)两个文件;
- **后端从未引用**:对 `backend/` grep `sync_service|from cloud` 零命中 → 云同步服务未集成进主应用，三端同步能力停留在文档与孤立代码;
- `cloud/README.md:483-489` 自称"完成云端架构设计/实现指南",准确说完成的是**设计**,不是可运行系统。

---

## 九、健康检查与优雅停机

**健康检查(实测 ✅,本项目少数扎实之处)**:
- `/health` 存活探针:`backend/app/main.py:665-673`,公开、无依赖;
- `/ready` 深度就绪探针:`main.py:689-744`,逐项检查 memory/trace/runs/workflows/audit 存储,qdrant/browser/langfuse 降级报告,503/200 语义正确;
- 另有 `backend/app/api/health_checks.py:197,206`(liveness/readiness)与 `backend/app/api/health.py:158,167` 两套并行实现,`health_router` 已挂载(`main.py:535`)—— 实现冗余但不冲突;
- **遗憾**: 所有 K8s/Helm 清单的 readinessProbe 都打 `/health` 而非 `/ready`(`deployment/k8s/xagent-api-deployment.yaml:132-139` 等),深度探针被浪费。

**优雅停机(部分 ✅)**:
- 应用层:`main.py:627-649` shutdown 钩子清理 MCP 管理器与 sandbox worker,✅;
- K8s 层:全仓**无任何 preStop 钩子**;`terminationGracePeriodSeconds` 仅出现在 `deployment/kubernetes/deployment.yaml:138`(30s)与文档示例中;`deployment/k8s/` 与 Helm 模板均未设置 → 滚动更新时长任务(Agent 执行)可能被 SIGKILL 硬切;
- uvicorn 默认处理 SIGTERM,但 compose 中 `API_WORKERS: 4`(`docker-compose.yml:154`)的多 worker 模式与 websocket/后台任务的亲和性未见说明(待验证)。

---

## 十、CI/CD 与其他运维面

- `.github/workflows/` 13 个流水线文件(ci/test/lint/security/deploy 等),`deploy-production.yml`(265 行)含镜像推送、helm upgrade、rollout status、失败自动 undo(`:245-247`)——结构完整，但因 Helm Chart 缺 worker 模板(§3.3),**首次真实执行必失败**;
- `.env.production`/`.env.test` 等环境样例存在;`deployment/env/README.md` 的变量说明仍是无前缀风格(`:6-20`),与 `DEPLOYMENT.md:7` 的前缀规则矛盾，易误导;
- `Makefile`、`deploy.sh`(根目录，ghcr.io + kubectl 流程)等多入口并存，未收敛。

---

## 十一、差距与提升方案(按优先级)

### P0 —— 不修则任何环境都跑不起来

1. **修复 compose 致命引用**:将 `docker-compose.yml:17` 指向真实存在的 `backend/migrations/init_schema.sql`(或补充 `deployment/migrations/init.sql`),并做一次全新卷的 `docker compose up` 冒烟验证;
2. **统一环境变量前缀**:全量替换 k8s/kubernetes/canary/helm/performance-compose 中的 `DATABASE_URL→XAGENT_DATABASE_URL`、`REDIS_URL→XAGENT_REDIS_URL`、`QDRANT_URL→XAGENT_QDRANT_URL` 等(`deployment/k8s/xagent-api-deployment.yaml:70-116`、`deployment/kubernetes/deployment.yaml:48-67`、`deployment/canary/canary-deployment.yaml:48-77`、`deployment/helm/templates/configmap.yaml:7-19`、`docker-compose.performance.yml:46-48`);
3. **Celery 二选一**:要么真实实现 `backend/app/workflow_worker.py` 的 Celery app(并补充任务定义),要么把所有编排中的 `celery -A ...` 命令改为 `python -m backend.app.workflow_worker` 并删除 celery 依赖与叙事。建议短期走后者，长期补前者;
4. **接线监控**:在 `main.py` 启动流程调用 `backend/app/monitoring/__init__.py:initialize_monitoring`(或手动挂载 PrometheusMiddleware + `/metrics`),删除/收敛其余三套 prometheus.yml,保留 `monitoring/prometheus/prometheus.yml` 为唯一权威并修正目标地址;
5. **修复监控 compose 挂载**:`monitoring/docker-compose.yml:10-11` 补挂 `recording_rules.yml`。

### P1 —— 商用交付前必须完成

6. **收敛部署资产为单一权威路径**:删除 `deployment/kubernetes/` 或 `deployment/k8s/` 其一;补全 Helm Chart(worker/beat/DB/CronJob 模板),修复 `values.yaml` 重复键(`:83/161`、`:97/165`、`:111/168`),让 CD 以 Helm 为唯一入口并真实跑通一次;
7. **readinessProbe 切换到 `/ready`**;所有 Deployment 增加 `terminationGracePeriodSeconds`(≥60s，覆盖长任务)与 preStop sleep;
8. **修复 Qdrant 备份/恢复**:`deployment/backup/backup.sh:94` 与 `DISASTER_RECOVERY.md:178,226,292` 改用官方快照 API(来源:[Qdrant Backup and Restore 文档](https://qdrant-qdrant-18.mintlify.app/operations/backup-restore),2026-03-04);增加备份 CronJob 与恢复演练记录;
9. **产出真实基准**:执行 `locustfile.py` 与 `benchmarks/run_benchmarks.py`,回填 `PERFORMANCE_BENCHMARK_REPORT.md` 占位符;删除或标注 `benchmarks/report_generator.py:524-556` 样例数据生成的报告，避免误导;
10. **状态外置**:为文件类 store(`settings.py:48-55`)提供 Postgres/Redis 后端的强制检查——生产模式下若检测到 sqlite/文件存储直接拒绝启动,HPA 才有意义。

### P2 —— 商用增强

11. 金丝雀引入 Argo Rollouts 或 Flagger 做权重路由，先把判据指标接通(依赖 P0-4);
12. 补齐 `deployment/runbooks/` 6 本 runbook 或修正 `DISASTER_RECOVERY.md:399-407` 引用;每季度至少一次 DR 演练并归档报告;
13. cloud/ 同步服务与主后端集成或明确标注为独立服务;镜像补齐 Playwright 依赖;
14. 告警 runbook_url 替换为真实链接;Grafana 管理员密码改为 secret 注入。

---

## 十二、要点摘要

1. **总体评分 2.0/10**:部署运维资产"数量"充足(4 套 Compose、2 套 K8s、Helm、监控、DR 文档共 60+ 文件),但交叉验证后多条主链路必坏，属于"文档驱动、未经执行验证"的状态。
2. **三个致命硬伤**:(a) `docker-compose.yml:17` 引用不存在的 init.sql;(b) K8s/Helm/Canary 全线使用无前缀环境变量，与 `settings.py:14` 的 `XAGENT_` 前缀冲突，Pod 会以 sqlite+只读根文件系统启动;(c) 全后端无 Celery 应用，所有 worker/beat 编排命令必然 CrashLoopBackOff。
3. **监控告警是空转**:`/metrics` 从未挂载,HTTP 指标中间件未接线，告警表达式引用的指标不存在，金丝雀脚本的自动回滚判据因此永远"通过",比没有更危险。
4. **性能数据为零**:根目录基准报告全占位符,`benchmarks/` 报告由硬编码样例数据生成(`report_generator.py:525`);locustfile 等工具真实存在但无一次执行结果。
5. **灾备体系文档完备、证据空白**:RTO/RPO 是目标值;Qdrant 备份/恢复 API 写错;引用的 runbooks 与脚本路径不存在;无任何演练记录,"99.99% 可用性"宣称无支撑。
6. **少数扎实点**:Dockerfile 多阶段+非 root+健康检查合格;`/health` 与 `/ready` 探针实现质量高;`backup.sh` 的 PG/Redis 部分与 `rollback.sh` 结构合理;HPA 配置写法规范(但状态未外置，启用即出错)。
7. **修复路径清晰**:按 P0(5 项)→P1(5 项)→P2(4 项)推进，预计 P0 完成即可让 Compose 单环境真实可用;P1 完成才具备"可演示的商用部署";当前状态距离"完整商用交付"的部署运维维度预估完成度约 **20%**。
