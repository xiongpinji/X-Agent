# X-Agent 深度独立审计报告

> 审计日期：2026-06-17
> 审计方式：完全独立，不依赖项目内任何既有审计报告（`audit_reports/` 本身已被 .gitignore 排除，亦未参考）。
> 证据来源：codegraph 代码图索引（2,383 个已索引文件 / 50,163 节点 / 107,848 边）、直接 Read 源码、Grep 全仓检索。
> 重要限制：本次会话隔离 Linux 沙箱**全程不可用**（持续 “Workspace still starting” / `ERR_CONNECTION_TIMED_OUT`），因此**未能实跑 pytest**。所有“测试能不能过”的结论均来自静态证据（CI 配置、pytest 配置、源码逻辑），并已明确标注。带 ≈ 的数字为单次采样估计，精确数字来自 codegraph 索引。

---

## 0. 一句话裁定

X-Agent 的**功能内核是真的**（鉴权、工作流引擎、RBAC、密钥治理都是实打实的代码），但它的**“交付就绪”叙事是被一层巨大的自证式治理/报告脚手架撑起来的**，而真正能拦住问题的关卡——CI 测试门禁——只跑了全套约 400+ 测试里的 **8 个文件**，并且把仓库自己定义的 70% 覆盖率红线在每次调用里用 `--no-cov` 显式关掉。

**结论：可作为“有真实内核的工程原型 / 内测候选”，但目前不具备“商业交付就绪”，主要不是因为内核差，而是因为质量保证（CI 门禁 + 覆盖率）是装样子的，无法支撑对外承诺。**

---

## 1. 项目真实规模（已核实）

| 指标 | 数值 | 来源 |
|------|------|------|
| 已索引文件 | 2,383 | codegraph status |
| Python 文件 | 1,854 | codegraph status |
| 路由（route 节点） | 1,023 | codegraph status |
| `backend/app/api/` 下 API 模块 | 200+ | codegraph files |
| 测试文件 `test_*.py` | ≈400+（顶层）+ 51（子目录） | 子目录精确，顶层为采样估计 |
| `backend/app/core/codex_*_readiness_packet.py` | **51** | codegraph files（精确） |
| `backend/app/core/integration_review_*.py` | **35** | codegraph files（精确） |
| `scripts/rc_*.py` 发布关卡脚本 | **25** | codegraph files（精确） |

这是一个**体量很大**的代码库（不是空壳），但体量分布严重偏向“治理/报告/关卡”层。

---

## 2. 安全与密钥防线（核实结论：内核真实可信，存在一处死代码隐患）

### 2.1 鉴权内核是真的 ✅（正面认定）

直接读 `backend/app/dependencies.py` 的 `get_current_principal` / `enforce_scope`，逻辑确实成立：

- **生产模式绝不回落匿名主体**：`dependencies.py:235` — `if settings.require_api_key or app_mode == "production": raise 401`。即便某条路由漏配 `enforce_scope`，生产模式下没有凭据也进不来。这是一个真正的纵深防御。
- **未认证主体零权限**：`security.py:131-138` `has_scope` 对 `authenticated=False` 直接返回 False；`RBACPolicy.resolve_scopes` 同样。
- **API Key 用 bcrypt（rounds=12）哈希 + 90 天过期 + 前缀索引**：`security.py:177-199`、`APIKeyStore.create`。不是明文比对。
- **bootstrap key 用 `compare_digest` 常数时间比较**，支持 sha256 形式（`_matches_bootstrap_key`）。
- **审计 HMAC 在生产强制**：`dependencies.py:159-163`，缺失时生产直接 `RuntimeError`，dev 才回落到临时 key。

> 这一层与“声称”一致，属于可信防线。

### 2.2 🟠 中危发现（本次新发现，此前审计未标注）：存在第二份分叉的鉴权实现 `dependencies_refactored.py`

- `backend/app/dependencies_refactored.py` 是 `dependencies.py` 的一份 360+ 行近似拷贝，**逻辑更弱**：
  - 它的 Bearer 路径仍用旧式 `_token_users.get(token)`（`dependencies_refactored.py:272-287`），**没有** `token_type`（access/refresh）区分，而正版 `dependencies.py:255-275` 已经用 `_principal_from_bearer_token(token, token_type=...)` 做了区分。
  - 它的 `get_audit_store` 直接 `RuntimeError("audit_hmac_secret must be configured")`，没有 dev 回落（与正版行为不一致）。
- **核实它是否被实际使用**：Grep 全仓 `dependencies_refactored` 只在 3 个 `docs/*.md` 出现，**没有任何 `.py` 导入它**（backend/tests/scripts 全扫）。codegraph callers 确认 `main.py`、`skill_curator.py` 用的都是正版 `dependencies.py`。
- **风险定性**：当前**不是活动漏洞**（没人 import 它），但它是一个 360 行的安全关键模块死代码副本。隐患在于：任何人若误 `from backend.app.dependencies_refactored import get_current_principal`，就会悄悄启用更弱的鉴权路径。属于“定时陷阱型死代码”。
- **建议**：删除 `dependencies_refactored.py`，或在文件顶部加 `raise ImportError("deprecated; use backend.app.dependencies")`。

### 2.3 仓库内真实密钥：核查通过 ✅

- Grep 全仓 `sk-…/ghp_…/AKIA…/BEGIN PRIVATE KEY` 仅命中 3 个测试文件，且全是**否定测试占位符**（如 `tests/test_owner_operator_commercial_delivery_intake.py:243` 的 `"sk-thismustnotbeaccepted123456"`、`AKIAIOSFODNN7EXAMPLE`）。无真实凭据被跟踪。
- `.gitignore` 的 secret hygiene 段（52-80 行）较完整：`*.pem/*.key/credentials*.json/*.kubeconfig/secrets.y*ml/dr-config.env/_secret_test.tmp`，并用 `!*.example` 放行模板。`data/api_keys.json` 等运行态密钥存储也已忽略（84、244 行）。

### 2.4 部署密钥防线（已知最近返工，独立复看一致）

`scripts/security_deployment_gate.py` 存在且为 import-safe 的弱口令/`:latest`/`--reload`/公网 DB 端口/硬编码密钥扫描器，逻辑自洽。**但注意**：该 gate 是否进 CI 门禁需结合第 4 节看——它只在 `.pre-commit-config.yaml` 里，而 pre-commit 依赖开发者本地安装，**不是服务端强制**。

---

## 3. 代码质量与真实性

### 3.1 功能内核是真实代码，不是桩 ✅

抽样核实了几个“最容易造假”的位置：

- **工作流引擎 `WorkflowExecutor.execute`（`backend/app/core/workflows.py:692-1013`）**：300+ 行真实实现——拓扑排序、逐节点执行、重试计数、补偿动作（compensation）、审批挂起（`WorkflowApprovalRequired`）、取消（`CancelledError`）、审计与事件记录、快照恢复游标。这是真引擎，不是 `return {"status":"ok"}`。
- **`sleep` 命中点**复查：均为合法用途（TS SDK `sdk-ts/src/task.ts` 轮询退避、partner SDK 重试退避），**未发现** `await asyncio.sleep(0.1); return success` 式的伪执行桩。
- `NotImplementedError` 仅在异常类型定义中出现，非散落的未实现占位。

> 内核真实性这一关，X-Agent 是过的。这点要明确肯定。

### 3.2 🟠 中危：巨量“自证式治理/报告脚手架”，机器生成痕迹明显

这是整个项目最突出的结构性问题：

- **51 个** `codex_*_readiness_packet.py`（`backend/app/core/`），每个都是同一套路：一个 `CONFIG` dict + 调用共享的 `_codex_readiness_packet_core.py`。逻辑本体只有共享核心那一份，51 个文件是配置化薄包装。
- **35 个** `integration_review_*.py`，命名出现明显的机器生成爆炸，例如：
  - `integration_review_manifest_adoption_tracker_owner_handoff.py`
  - `codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet.py`（**一个文件名 84 字符**）
- **25 个** `scripts/rc_*.py` 发布关卡 + 对应 25 个 `test_rc_*.py`。
- **直接物证**：`.gitignore:246-247` 写着
  > `# Codex recursive scaffold (orphaned, path too long to delete)`
  > `backend/app/core/integration_review_manifest_adoption_tracker_notif*`

  这是项目自己承认：自动化脚手架生成了**路径长到在 Windows 上删不掉**的孤儿文件。这是“脚手架失控”的铁证。

**定性**：这些不是假代码（它们能跑、有测试），但它们是**过程/治理报告层**，不是产品功能。它们让“文件数 / 测试数 / 完成度”在观感上暴涨，却几乎不增加对最终用户的产品价值。一个真正要商业交付的 Agent 框架，核心竞争力应是 agent/workflow/memory/tool，而不是 50+ 个“就绪度证据包”校验器。

### 3.3 🟡 低危：`.gitignore` 编码损坏（mojibake）

`.gitignore` 第 115–238 行存在大量乱码中文注释（`# ����ʱԭ��д��ʱ�ļ�`），说明该文件某次被以错误编码写入。功能不受影响（规则仍生效），但属于明显的工程卫生瑕疵，且与本项目历史记录的“CJK 路径 + 工具回写”陷阱吻合。

---

## 4. 测试与 CI 真实基线（最严重的问题域）

### 4.1 🔴 高危：CI 只跑全套测试的极小子集，"全套测试"从不在 CI 跑

直接读 `.github/workflows/ci.yml`（主 CI/CD Pipeline）与 `.github/workflows/test.yml`（Test Suite）：

**`ci.yml` 的 `pilot-gate` / `test` job 实际只跑：**
```
tests/test_workbench_bff.py
tests/test_lite_mode.py
tests/test_security.py::test_workflow_run_ignores_client_tenant_id   ← 单个测试函数
tests/test_observability.py
+ 4 个 test_commercial_pilot_*.py 合同测试
```
（`ci.yml:43-64`、`87-93`）

**`test.yml` 同样：**
- `unit-tests`：和上面一样那 4 个文件（`test.yml:71-75`）
- `integration-tests`：只跑 `tests/test_workbench_bff.py` 一个文件（`:155`），且 PR 上 `continue-on-error: true`（`:156`）
- `contract-tests`：只跑 `test_security.py::test_workflow_run_ignores_client_tenant_id` 单个函数（`:211`）
- `performance-tests`：`pytest tests/ -m performance ... || true`（`:269`，失败被吞）

**也就是说：开发者可以把代码合进 `main`/`develop`，而 ≈400 个测试里只有约 8 个文件真正拦路。** 其余几百个 `test_codex_*` / `test_commercial_*` / `test_rc_*` / `tests/enterprise/**` / `tests/e2e/**` 从不在 CI 门禁中执行。

### 4.2 🔴 高危：仓库自定义的 70% 覆盖率红线被 CI 每次显式关闭

- `pytest.ini:13-22` 明确要求 `--cov=backend --cov-fail-under=70 --strict-markers`。
- 但 CI 每个 pytest 调用都带 `-o addopts=--no-cov`（`ci.yml:49,64,93`；`test.yml:75,155,212`），**把覆盖率门禁整段覆盖关掉**。
- 结果：项目对外可声称“有 70% 覆盖率门禁”，实际 CI 从不计算覆盖率，更不会因覆盖率失败。

### 4.3 🟠 中危：`test-summary` 硬编码“通过”

`test.yml:289-295` 的汇总步骤直接 `echo "- Integration Tests: ✓"`、`"- Contract Tests: ✓"`——**无视真实结果**写死打勾。这是 over-report 的典型：摘要产物看起来全绿，与实际门禁状态脱钩。

### 4.4 🟡 其他 CI 卫生问题

- `lint` job 只对**硬编码的 14 个文件**跑 ruff（`ci.yml:112-132`），不是全代码库。
- `security` job 的 Bandit 与 pip-audit 都是 `continue-on-error: true`（`ci.yml:150,155`），失败不阻断。
- `test.yml` 的服务容器用 `qdrant/qdrant:latest`（`:47,131,187,244`）——可变 tag，与项目自己的部署硬化规则（禁 `:latest`）自相矛盾。
- 部署硬化 gate (`security_deployment_gate.py`) 只挂在 pre-commit（客户端、可绕过），**没有进服务端 CI 强制**。

### 4.5 关于“测试真实绿率”——本次无法实跑

沙箱全程不可用，未能跑 pytest。因此**无法给出当前真实 pass/fail 数字**。能确证的是：项目历史与 CLAUDE.md 自述基线为“3856 passed / 76 fail / 4 err”，但**该基线只能在用户本机跑**，且**从未被 CI 验证过**——这正是 4.1 的风险所在：没有任何自动化关卡在持续验证这个数字，它随时可能已经漂移而无人知晓。

---

## 5. 商业交付就绪度裁定

| 维度 | 裁定 | 依据 |
|------|------|------|
| 功能内核真实性 | ✅ 真实 | workflow/auth/RBAC/密钥治理均为实打实代码 |
| 安全防线 | 🟢 基本成立，1 处死代码隐患 | 生产不回落匿名 + bcrypt + HMAC 强制；`dependencies_refactored.py` 应删 |
| 仓库密钥卫生 | ✅ 干净 | 无真实凭据被跟踪，.gitignore 覆盖到位 |
| 代码质量/真实性 | 🟠 内核真实但治理脚手架严重过度 | 51+35+25 个机器生成报告/关卡文件，含承认删不掉的孤儿 |
| **测试与 CI 门禁** | 🔴 **不达标** | 全套测试从不在 CI 跑；70% 覆盖率被 `--no-cov` 关闭；摘要硬编码✓ |
| 整体商业交付就绪 | 🔴 **未就绪** | 不是内核不行，而是质量保证装样子，无法支撑对外承诺 |

### 为什么“未就绪”的根因不是功能，而是信任链

一个商业交付的核心，是**“声称的质量”能被自动化持续证明**。X-Agent 当前：
- 有大量“就绪度/交付/发布关卡”脚手架（看起来非常“可交付”）；
- 但真正的质量关卡（CI 测试 + 覆盖率）只验证了约 2% 的测试面，且把覆盖率红线关掉、把摘要写死为通过。

这形成一个**危险的反差**：治理外观极重，实际门禁极轻。对内部原型无所谓，对商业交付是致命的——因为你无法在回归发生时被自动拦住。

---

## 6. 优先级修复建议

**P0（阻断商业交付，必须先做）**
1. **让 CI 真正跑全套测试**：把 `ci.yml`/`test.yml` 的 cherry-pick 列表替换为 `pytest tests/`（可分片并行避免超时），并先在本机产出真实 pass/fail 基线。
2. **恢复覆盖率门禁**：移除 CI 里的 `-o addopts=--no-cov`，让 `--cov-fail-under=70` 真正生效（或显式下调到当前真实值并写明，而不是关掉）。
3. **删除 `test-summary` 里硬编码的 `✓`**，改为读取真实 job 结论。

**P1（安全与质量）**
4. 删除或封死 `backend/app/dependencies_refactored.py`（防止误用更弱鉴权路径）。
5. 把 `security_deployment_gate.py` 接入服务端 CI（不只 pre-commit）；同时把 `test.yml` 里的 `qdrant/qdrant:latest` 钉到固定版本。
6. 让 `lint` / `security` job 覆盖全代码库，且 security 失败应阻断（去掉 `continue-on-error`，或分级）。

**P2（工程卫生 / 减重）**
7. 评估 51 个 `codex_*_readiness_packet` + 35 个 `integration_review_*` 的真实价值，合并/精简这层治理脚手架；清理 `.gitignore:247` 承认的孤儿 scaffold。
8. 用正确编码重写 `.gitignore`，消除 mojibake 注释。

---

## 7. 审计方法与诚实边界

- **已独立核实**（不依赖任何现成报告）：鉴权逻辑、RBAC、密钥治理、workflow 引擎真实性、CI 配置、pytest 配置、仓库密钥扫描、脚手架文件计数、dependencies_refactored 的导入情况——全部来自 codegraph 索引 + 直接 Read + Grep。
- **未能验证**：本会话沙箱全程不可用，**未实跑 pytest**，因此“当前真实绿率”无法给出；带 ≈ 的测试文件总数为单次采样估计。codegraph 索引可能与磁盘存在最多约 1 秒的写入延迟，但本审计涉及的文件均为既有文件，不受影响。
- **没有修改任何文件**：本次为纯审计，未改动代码。

> 如需，我可以在沙箱恢复后实跑 `pytest tests/`（分片）产出真实绿率基线，把第 4.5 节的空缺补上。
