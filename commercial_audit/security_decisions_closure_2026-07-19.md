# 安全决策关闭报告（P0-08）

- **角色**：安全决策关闭工程师
- **日期**：2026-07-19
- **任务**：逐项关闭 `SECURITY_DECISIONS.md` D-1~D-4 悬置决策；核验 D-3 git 历史密钥清洗状态；对当前工作树做密钥扫描（只读）
- **范围**：`SECURITY_DECISIONS.md` 及安全相关文档；未修改任何 backend 代码（密钥发现仅报告）
- **仓库基线**：commit `f3aab93`（2026-07-19 fresh init 后的唯一提交）

---

## 一、结论摘要

| 决策 | 原风险级 | 结论 | 核心依据 |
|---|---|---|---|
| D-1 生产强制 API Key | MEDIUM | ✅ 关闭（采纳方案 A） | `.env.production:82` 已 `=true`；`DEPLOYMENT.md:78,102` 已文档化 |
| D-2 Webhook HMAC secret | LOW | ✅ 关闭（采纳方案 A，且生产 WARNING 已在位） | `.env.production:44` 占位符；`settings.py:129-137` 生产空值告警 |
| D-3 git 历史密钥 | HIGH | ✅ 关闭（风险经仓库重建彻底消除，2 项后续已跟踪） | `git rev-list --all --count`=1；旧历史不可达；工作树扫描 0 真实密钥 |
| D-4 高危工具审批流 | LOW | ✅ 关闭（采纳推荐方案） | `settings.py:67` 默认 false；`.env.production:70` false；`DEPLOYMENT.md:57-61` 已文档化 |

**四项决策全部关闭，无悬置项。** 其中 D-3 附 1 项需 owner 一句话确认的事项（旧仓库是否曾外发，决定是否轮换密钥）与 1 项新发现的残留风险（`.env.*` 文件被新仓库跟踪），详见 §5。

---

## 二、逐项决策关闭详情

### D-1 生产强制 API Key —— 关闭，采纳方案 A

**原问题**：`XAGENT_REQUIRE_API_KEY=false` 同时出现在开发档与 docker-compose 默认值中，无网关部署时 API 裸奔。

**2026-07-19 核验证据**：
- `.env.production:82` —— `XAGENT_REQUIRE_API_KEY=true`（生产档已强制）
- `DEPLOYMENT.md:78,102` —— 两个生产部署 profile 均写 `XAGENT_REQUIRE_API_KEY=true`；`DEPLOYMENT.md:114` 明确仅本地开发用 `false`
- `backend/app/settings.py:20` —— 代码默认值 `false` 保留（开发便利），生产值经环境变量注入

**结论**：方案 A（生产默认开启 + 文档化）已实质落地，决策关闭。方案 B（生产模式下未开启时启动 WARNING）未实现，因方案 A 已生效而判定无必要。

**残留（非阻塞，见 §5.3）**：`docker-compose.yml:136,211` 仍为 `${XAGENT_REQUIRE_API_KEY:-false}` 兜底，且 compose 无 `env_file:` 接线 `.env.production`——操作者须显式导出变量或遵循 DEPLOYMENT.md。

### D-2 GitHub Webhook HMAC secret —— 关闭，采纳方案 A

**原问题**：生产环境 `XAGENT_GITHUB_WEBHOOK_SECRET` 为空则 webhook 无鉴权。

**2026-07-19 核验证据**：
- `.env.production:44` —— `XAGENT_GITHUB_WEBHOOK_SECRET=REPLACE_WITH_GENERATED_SECRET`（占位符已在位，方案 A 落地）
- `DEPLOYMENT.md:104` —— 已文档化
- `backend/app/settings.py:129-137` —— 生产模式空 secret 启动时记 WARNING（方案 B 的弱化形式已在位）
- 验签实现本体（`X-Hub-Signature-256`、HMAC-SHA256、恒定时间比较）经 `commercial_audit/12_security_compliance_audit.md` 确认无虞

**结论**：关闭。残留建议：validator 由 WARNING 升级为生产 fail-fast（P1，见 §5.4）。

### D-3 git 历史密钥清洗 —— 关闭（风险已由仓库重建彻底消除）

**原问题**：`data/api_keys.json`（可能含真实 API key 哈希）曾进入 git 历史，任何 clone 者可读取历史内容；审计时因仓库无 `.git` 无法验证，标注"待验证"。

**2026-07-19 核验证据**（命令与输出见 §6）：
1. **仓库已于 2026-07-19 重建 git（fresh init，无历史）**：`git rev-list --all --count` = 1，唯一提交为 `f3aab93 chore: 商用修复基线快照 (审计前状态, 2026-07-19)`；`git remote -v` 为空（无远程）；`git fsck` 无悬空对象。**旧历史在本机以任何形式均不可达**，`git filter-repo`/BFG 清洗既不需要也不可能执行——方案 A 的目标（历史不再含密钥）已以更彻底的方式达成。
2. **`data/api_keys.json` 三态核验**：工作树中物理不存在（`data/` 仅含被 gitignore 的运行时文件）；未被 git 跟踪（`git ls-files data/` 为空）；已被 `.gitignore:38` 与 `.gitignore:196` 双重覆盖。
3. **当前工作树密钥全量扫描：0 项真实密钥**（详见 §4）。
4. 遗留脚本 `cleanup_sensitive_info.py`（为旧仓库编写的 filter-repo 助手，内嵌旧项目绝对路径）已失效，建议归档或删除（范围外，见 §5.5）。

**结论**：历史维度关闭。**密钥轮换维度需 owner 确认**：本地清洗不能吊销已外流的副本——若重建前的旧仓库曾 push 到任何远程或分发给第三方，当时使用的全部 API 密钥仍必须轮换；若旧仓库从未离开本机，则无需轮换。（旧仓库分发范围本代理无法验证，见 §5.2。）

**纪律说明**：原文档"未经明确批准不得修改这些文件"的指示已遵守——未改动任何数据文件，扫描全程只读。

### D-4 `enable_high_risk_tools` 生产审批流 —— 关闭，采纳推荐方案

**原问题**：开启该开关将允许 write_file / apply_text_patch / apply_batch_patch 无人审批执行。

**2026-07-19 核验证据**：
- `backend/app/settings.py:67` —— 默认 `False`
- `.env.production:70` —— `XAGENT_ENABLE_HIGH_RISK_TOOLS=false`
- `DEPLOYMENT.md:57-61` —— 文档化显式开启方式并警告"不要将 `=true` 作为生产广泛默认"；`DEPLOYMENT.md:85` 生产清单保持 `false`
- 审批存储可用：`settings.py:53` `approval_store_path` 默认 `data/approvals.json`；`.env.production:35` 留空即回落默认存储

**结论**：推荐方案（保持 false 默认 + 显式 env 开启 + 配合审批存储记录/闸门）即为当前实现与文档状态，决策关闭。

---

## 三、D-3 专项：git 历史状态核验记录

| 核验项 | 命令 | 结果 |
|---|---|---|
| 全部历史提交数 | `git rev-list --all --count` | `1` |
| 提交清单 | `git log --all --oneline` | 仅 `f3aab93 chore: 商用修复基线快照 (审计前状态, 2026-07-19)` |
| 远程配置 | `git remote -v` | 空（无远程） |
| 悬空对象 | `git fsck --lost-found` | 无输出（无不可达对象） |
| `data/api_keys.json` 跟踪状态 | `git ls-files data/` | 空（整个 `data/` 未被跟踪） |
| gitignore 覆盖 | 检查 `.gitignore` | 第 38、196 行均含 `data/api_keys.json` |

**判定**：旧历史（含 `data/api_keys.json` 的历史版本）已随 fresh init 彻底消失，审计报告中的"待验证"项就此关闭。

---

## 四、当前工作树密钥扫描清单

### 4.0 扫描方法

- **范围**：整个工作树。Grep 工具默认遵守 .gitignore（即覆盖全部 git 跟踪文件）；另用 shell grep 补扫被工具安全过滤的 `.env.*` 文件（其中 5 个被 git 跟踪，必须覆盖）及 gitignore 内的运行时目录 `data/`、`logs/`、`.xagent_runtime/`。
- **模式**：`sk-[A-Za-z0-9_-]{10,}`、`AKIA[0-9A-Z]{16}`、`-----BEGIN ... PRIVATE...-----`、`password|passwd|pwd\s*[:=]`、`ghp_*`、`github_pat_*`、`xox[baprs]-*`、`AIza*`、`sk_live_*`/`rk_live_*`、`SG.*`、`hf_*`、`dop_v1_*`、JWT（`eyJ*`）、bcrypt 哈希（`$2[aby]$*`）、`xag_[A-Za-z0-9]{20,}`、高熵值 `(secret|token|private_key|apikey|api_key|access_key)=["']…{24,}["']`。
- **性质**：只读扫描，未修改任何文件。

### 4.1 真实硬编码密钥：**0 项**

未发现任何真实的云厂商凭证（AKIA/AIza/xox/ghp 真实形态）、私钥 PEM、JWT、bcrypt 哈希、真实 API key。全部命中均为下列三类（占位符/示例、测试伪值、弱默认口令）。

### 4.2 被 git 跟踪的 env 类文件核验（8 个）

| 文件 | 跟踪状态 | 内容核验结论 |
|---|---|---|
| `.env.production` | **被跟踪** | 全部敏感项为占位符（`REPLACE_WITH_GENERATED_*`），无真实值；但文件本身不应被跟踪（见 §5.1） |
| `.env.development` | **被跟踪** | 含可预测 dev 占位值：`XAGENT_AUDIT_HMAC_SECRET=dev-hmac-secret-change-in-production`（:34）、`XAGENT_JWT_SECRET=dev-jwt-secret-change-in-production-min-32-chars`（:63）；`XAGENT_REQUIRE_API_KEY=false`（:70） |
| `.env.test` | **被跟踪** | 测试占位值：`test-hmac-secret`（:34）、`test-jwt-secret-min-32-chars-for-testing`（:63） |
| `.env.performance` | **被跟踪** | `DB_PASSWORD=postgres`（:12，弱默认） |
| `.env.example` | 被跟踪（gitignore 显式豁免） | 占位符 `sk-your-openai-api-key-here` 等（:64-66），合理 |
| `deployment/.env.monitoring.example` | 被跟踪 | 示例文件，未命中真实密钥模式 |
| `frontend/.env.example` | 被跟踪 | 示例文件，未命中真实密钥模式 |
| `monitoring/.env.example` | 被跟踪 | 示例文件，未命中真实密钥模式 |

注：根目录**不存在** `.env` 文件（已核验）。`.gitignore:33` 的 `*.env` 模式不匹配 `.env.<name>` 命名，是前 4 个文件被跟踪的直接原因。

### 4.3 占位符 / 文档示例 / 测试伪值命中（低危，择要列出）

| 文件:行号 | 内容性质 |
|---|---|
| `.claude/skills/tech-debt-tracker/assets/sample_codebase/src/user_service.py:14` | 教学样例 `API_KEY = "sk-1234567890abcdef"`（自带 FIXME 注释，故意为之的反例素材） |
| `docs/CONFIG_MIGRATION.md:215`、`docs/CONFIG_BEST_PRACTICES.md:148,165`、`docs/tutorials/03-memory-system.md:142` | 文档示例 `sk-1234567890` |
| `docs/ENVIRONMENT.md:155,317,349`、`docs/tutorials/GETTING_STARTED.md:52-53`、`docs/faq/README.md:59`、`docs/video-scripts/README.md:41` | 文档占位符 `sk-your-*` |
| `docs/MCP_PLUGIN_USER_GUIDE.md:159`、`docs/MCP_PLUGIN_EXAMPLES.md:104`、`plugins/INSTALLATION_GUIDE_ZH.md:154,167,175`、`plugins/QUICKSTART_ZH.md:84,92` | 文档占位符 `ghp_xxxx…` |
| `docs/API_INTEGRATION_GUIDE_NEW.md:299`、`docs/THIRD_PARTY_INTEGRATION.md:254` | 文档占位符 `xoxb-your-token` / `xoxb-YOUR-TOKEN` |
| `templates/k8s-deployment.yaml:23` | 占位符 `sk-ant-CHANGE_ME` |
| `backend/app/core/billing_init.py:225` | 代码内占位符 `"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"`（省略号，非真实私钥） |
| `tests/test_rc_owner_gate_plan.py:207,219` | 测试伪值 `sk-test-value`（且该测试断言密钥须被脱敏） |
| `tests/test_security_hardening.py:182` | 测试字符串 `xag_abcdef1234567890abcdef1234567890`（用于验证脱敏） |
| `tests/test_config.py:111`、`tests/test_security_fixes.py:79,87,212,221,239,247` | 测试用 JWT secret 伪值 |
| `docs/partner_integration_guide.md:457` | 文档示例 `xag_partner_abc123def456xyz789abc123def456`（形态逼真但为示例） |
| `k8s/deployment.yml:28`、`backend/app/core/enterprise_deployment.py:49,682` | 占位符 `your-secret-key-min-32-characters-long` / `CHANGE_ME_*` |

### 4.4 弱默认口令清单（非泄露的真实密钥，但为硬编码弱默认，供后续加固参考）

| 文件:行号 | 项 | 评估 |
|---|---|---|
| `docker-compose.yml:10,36,85,117-118,150-151,192-193,215-216,243-244,250-251` | 兜底默认值 `xagent_secure_password` / `redis_secure_password` / `neo4j_secure_password` | 本地开发兜底；生产必须经 env 覆盖（DEPLOYMENT.md 已要求） |
| `docker-compose.yml:60,120,195` | `QDRANT_API_KEY` 兜底 `qdrant_secure_key` | 同上 |
| `docker-compose.test.yml:17,43,92,127-234`（多处） | `test_password_123` / `test_redis_123` / `test_neo4j_123` | 测试环境专用，可接受 |
| `docker-compose.test.yml:326` | `GF_SECURITY_ADMIN_PASSWORD=admin` | 测试 Grafana，弱但仅限测试栈 |
| `docker-compose.test.yml:501` | `ELASTICSEARCH_PASSWORD=changeme` | 同上 |
| `.github/workflows/test.yml:26,106,162,218`、`ci.yml:81,155`、`ci-cd.yml:123` | `POSTGRES_PASSWORD: xagent` | CI 临时容器，生命周期限于单次 job，低危 |
| `.github/workflows/test-environment.yml:89` | `POSTGRES_PASSWORD: test_password_123` | 同上 |
| `.github/DEPLOYMENT-GUIDE.md:20,52,524` | 文档示例 `POSTGRES_PASSWORD=xagent` | 文档 |
| `cloud/DEPLOYMENT_GUIDE.md:94,114,154-155,198,203,259-260` | 文档示例 `xagent_secure_password` 等 | 文档 |
| `database_benchmark.py:535` | `password="postgres"` | 本地基准脚本默认值 |
| `backend/local/tests.py:291` | `password = "mypassword"` | 测试文件 |
| `ARCHITECTURE_OPTIMIZATION_INTEGRATION_GUIDE.py:255` | `"my_secret_password"` | 示例代码 |
| `backend/docs/SSO_CONFIGURATION.md:98,157` | `LDAP_BIND_PASSWORD=password` | 文档示例 |
| `.claude/skills/performance-profiler/references/profiling-recipes.md:423` | `password: 'loadtest123'` | 教学文档示例 |
| `.env.performance:12` | `DB_PASSWORD=postgres` | 被跟踪 env 文件内的弱值（见 §5.1） |

### 4.5 误报说明

- `frontend/src/pages/AgentWorkspace.tsx:164` / `AgentWorkspace.css:233`：CSS 类名 `task-input-form` 恰好匹配 `sk-[A-Za-z0-9_-]{10,}`，非密钥。
- `commercial_audit/node_modules/**`：工具链依赖类型定义，非本项目资产，已忽略。

---

## 五、残留风险与下一步建议

1. **【需编排者/owner 执行，本代理无 git 写权限】`.env.*` 被新仓库跟踪**：`.env.development`、`.env.performance`、`.env.production`、`.env.test` 已进入基线提交 f3aab93。当前内容经核验均为占位符/dev/test 值（§4.2），但一旦有人往其中写入真实密钥并提交，将重演 D-3。建议：(a) `git rm --cached` 四个文件；(b) 修正 `.gitignore` 模式（如增加 `.env.*` 并保留 `!.env.example` 豁免）；(c) 保持"只提交占位符"纪律。
2. **【需 owner 一句话确认】密钥轮换**：重建前的旧仓库是否曾 push 到远程或分发给第三方？若是 → 轮换当时全部 API 密钥；若否 → 无需动作。本代理无法验证旧仓库分发范围。
3. **【建议移交部署加固批次】compose 生产接线缺口**：`docker-compose.yml:136,211` 的 `XAGENT_REQUIRE_API_KEY` 兜底仍为 `:-false`，且无 `env_file:` 引用 `.env.production`；根目录无 `.env`。建议将生产服务兜底改为 `:-true` 或在 compose 中显式接线 env 文件（属 P0-01/02/03 部署范围）。
4. **【P1 建议】webhook secret validator 升级**：`settings.py:129-137` 生产空值仅 WARNING，建议升级为 fail-fast（与 JWT_SECRET 等校验强度对齐）。
5. **【范围外清理建议】失效脚本**：`cleanup_sensitive_info.py` 为旧仓库编写且内嵌旧项目绝对路径（`X-Agent 原创内核计划`），已失效，建议归档或删除。

---

## 六、验证命令与结果

| # | 命令 | 结果 |
|---|---|---|
| 1 | `git rev-list --all --count` | `1` —— 全仓库仅 1 个提交 |
| 2 | `git log --all --oneline` | 仅 `f3aab93`（2026-07-19 基线） |
| 3 | `git remote -v` | 空 —— 无远程，旧历史不可达 |
| 4 | `git fsck --lost-found` | 无悬空对象 |
| 5 | `git ls-files` 过滤 `data/`、`.env` | `data/` 零跟踪；`.env.development/.example/.performance/.production/.test` 等 8 个 env 类文件被跟踪 |
| 6 | `ls -la data/` | 无 `api_keys.json`；仅 gitignored 运行时文件 |
| 7 | `git check-ignore -v .env.production …` | 无输出 —— 四个 `.env.*` 均未被 ignore |
| 8 | Grep 高信号密钥模式（全仓） | 0 真实密钥；命中均为 §4.3 占位符/示例 |
| 9 | shell grep 补扫 5 个被跟踪 `.env.*` + `data/`、`logs/`、`.xagent_runtime/` | 0 真实密钥命中 |
| 10 | `grep password=…`（全仓） | 命中均为 §4.4 弱默认/示例/测试值 |
| 11 | JWT（`eyJ*.…`）与 bcrypt（`$2*$`）模式 | 0 命中 |
| 12 | 复核 `settings.py:100-150`、`admin.py:235` | "已加固"声明属实；密码散列实为 bcrypt（文档已更正） |

文档类改动不适用"模块可导入"验证；以上 12 项即为本任务（只读核验 + 文档更新）的全部针对性验证，均可复核。

---

## 七、范围外发现的问题（仅记录，未处理）

1. `docker-compose.yml` 生产服务 `XAGENT_REQUIRE_API_KEY` 兜底 `:-false` 且无 env 文件接线（见 §5.3，属部署范围 P0-01/02/03）。
2. `cleanup_sensitive_info.py` 失效且内嵌旧项目绝对路径（见 §5.5）。
3. `settings.py:129-137` webhook 空 secret 仅 WARNING 不 raise（见 §5.4，建议 P1）。
4. 安全审计分报告指出的 `access_control.py:90-92` 允许 `?api_key=` 查询参数传 key（中间件未挂载，记录备查，属代码范围）。
5. `.claude/skills/tech-debt-tracker/` 样例资产含故意的硬编码反例（§4.3 首行），为教学素材，是否保留由 owner 决定。

---

*报告完 · 安全决策关闭工程师 (P0-08) · 2026-07-19 · 全部结论可经 §6 命令在当前工作树复核。*
