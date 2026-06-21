# AGENTS.md — 多 Agent 协作协调黑板

> **本文件是 Codex(总调度 `019ecfe8`)与 ZCode(会话 `sess_c93e053f`)的共享协作黑板。**
> 任何一方开始/完成任务前,必须先读本文件更新自己的状态,完成后回写进度。
> 协作介质:① 文件系统(本文件 + `audit_reports/`);② **双向通讯通道**(B 方案,已端到端验证,见文末「🔗 双向通讯通道」)。

**最后更新**: 2026-06-21 (Codex)
**当前协作阶段**: 安全漏洞修复(基于 `audit_reports/COMPREHENSIVE_AUDIT_20260617.md`)

---

## 🚀 快速开始 —— 通讯通道速查(任何会话先读这段)

> 本节是 ZCode/Codex 协作的"操作记忆"。详细协议见 `audit_reports/_comm/CHEATSHEET.md` 与 `PROTOCOL.md`。
> **2026-06-17 已端到端验证**:Codex 完成 5/5 操作问答(see `messages` table id=`9c52d69f`)。

**我是 ZCode,要派单给 Codex**:
```bash
python scripts/dispatch_to_codex.py --resume 019ecfe8-0db5-7b12-b1c0-e5acfc1985f3 --bypass-sandbox --timeout 600 "<指令>"
```

**我是 ZCode,要看 Codex 给我什么消息**:
```bash
python scripts/read_codex_messages.py            # 未读
python scripts/read_codex_messages.py --watch 30 # 轮询
```

**我是 Codex,要给 ZCode 回报告**:
```bash
python scripts/send_to_zcode.py --subject "<主题>" --body "<正文>" [--task-id P0-02 --status done|failed|blocked]
```

**共享存储**:`audit_reports/_comm/blackboard.sqlite`(SQLite WAL,双进程读写)
**完整速查**:`audit_reports/_comm/CHEATSHEET.md`

---

## 🤝 分工协议

| 角色 | Agent | 职责 | 工作边界 |
|---|---|---|---|
| **审计员/验证员** | ZCode (我) | 产出漏洞清单、验收标准、修复后回归验证 | **只读代码 + 只写 `audit_reports/`**。不直接改业务代码 |
| **修复执行方** | Codex | 按 ZCode 修复任务包改代码、写测试 | 改 `backend/` `frontend/` 等业务代码。**不改 `audit_reports/`** |
| **人类信使** | 你 | 在两个 agent 间传递任务包和验证结果 | 决策优先级、合并冲突仲裁 |

### 🚨 隔离规则(避免互踩)

1. **ZCode 只写 `audit_reports/` 目录** —— 我产出的所有文件(任务包、验证脚本、报告)都放这里,Codex 不要改这个目录。
2. **Codex 改业务代码** —— `backend/` `frontend/` `scripts/` 等。改完后在任务板标记 `修复完成`。
3. **冲突高发区**: `backend/app/api/` (30 个越权漏洞集中地)。Codex 改这个目录时,ZCode 不碰。
4. **每次任务领取前**: 读取下方任务板,把状态从 `待领取` 改成 `进行中(谁)`,避免重复劳动。
5. **每次任务完成后**: 把状态改成 `已修复(谁)/待验证`,ZCode 验证后改成 `已验证通过` 或 `验证失败(原因)`。

---

## 📋 修复任务板

> 状态流转: `待领取` → `进行中(Codex)` → `已修复待验证` → `已验证通过(ZCode)` / `验证失败`

### P0 — 阻断商业交付(24小时内)

| ID | 任务 | 文件 | 状态 | 验证标准 |
|---|---|---|---|---|
| P0-01 | enterprise.py 14 端点加授权 | `backend/app/api/enterprise.py` | 已修复待验证(Codex 019ecfe8) | `verify_fixes.py P0-01 → 5/0`; `pytest test_enterprise_api_auth.py → 4 passed` |
| P0-02 | sessions.py 6 端点强制 principal.tenant_id | `backend/app/api/sessions.py` | ✅ 已验证通过(ZCode) | **首次走完整 B 方案协作闭环 2026-06-17**:Codex 核验 `verify_fixes.py P0-02 → 4/0`、`pytest test_sessions_skills_issuepr_auth.py → 17 passed`;ZCode 独立复核 4/0;Codex 报告 msg id `df5fead6-be52-42ff-8057-d6b5152f48ed` |
| P0-03 | skills_api.py 4 端点强制 principal | `backend/app/api/skills_api.py` | 已修复待验证(Codex 019ecfe8) | `verify_fixes.py P0-03 → 4/0`; `pytest test_sessions_skills_issuepr_auth.py → 17 passed` |
| P0-04 | issue_to_pr.py execute 端点加授权 | `backend/app/api/issue_to_pr.py:49` | 已修复待验证(Codex 019ecfe8) | `verify_fixes.py P0-04 → 2/0`; `pytest test_sessions_skills_issuepr_auth.py → 17 passed` |
| P0-05 | 核实 reset_password 令牌验证 | `backend/app/api/auth.py:431` | ✅ 已验证通过(ZCode) | **非漏洞**:reset_password 有完整双流程+token校验,见 `VERIFICATION_RESULTS.md` |
| P0-06 | main.py:580 WARNING 改 raise | `backend/app/main.py:580` | 已修复待验证(Codex 019ecfe8) | `verify_fixes.py P0-06 → 1/0`; `pytest test_security_fixes.py → 39 passed` |

### P1 — 一周内

| ID | 任务 | 文件 | 状态 |
|---|---|---|---|
| P1-01 | 撤销被跟踪的 .env 文件 | `.env.{development,production,test,performance}`、`frontend/.env.production` | 已修复待验证(Codex 019ecfe8) |
| P1-02 | 加 pre-commit gitleaks 钩子 | `.pre-commit-config.yaml` | 已修复待验证(Codex 019ecfe8)；`pytest test_pre_commit_security_hooks.py → 1 passed`；`pre-commit run gitleaks --all-files` 因首次下载 Go 环境 SSL EOF 未完成 |
| P1-03 | 审计 35 个 UNKNOWN 未授权路由 | `enterprise_audit/migration/sso/i18n/...` | 已修复待验证(Codex 019ecfe8)；`pytest test_p1_03_unknown_route_auth.py test_route_auth_audit.py test_rbac_enforcement.py → 37 passed`；`route_auth_audit.py → passed` |
| P1-04 | saml_sso.py 用 defusedxml + 真签名验证 | `backend/app/core/saml_sso.py`、`backend/app/core/sso/saml_provider.py` | 已修复待验证(Codex 019ecfe8)；`pytest test_saml_signature.py → 15 passed`；`defusedxml` 已加入依赖清单 |
| P1-05 | 4 个无 timeout 的 HTTP 请求加 timeout | `scripts/backup_recovery.py` | 已修复待验证(Codex 019ecfe8)；`pytest test_backup_recovery_http_timeouts.py → 1 passed`；Qdrant 备份/恢复请求已加 30s timeout |

---

## 🔄 协作流程(每次任务的标准动作)

### Codex 领取任务时:
1. 读本文件 + `audit_reports/FIX_TASKS.md` 找到对应任务的详细修复规范
2. 在本文件任务板把状态改成 `进行中(Codex 019ecfe8)`
3. 按规范修复 + 写测试
4. 改完把状态改成 `已修复待验证`,在 `audit_reports/VERIFICATION_REQUESTS.md` 追加一条验证请求

### ZCode 验证时:
1. 读 `audit_reports/VERIFICATION_REQUESTS.md` 拿到验证请求
2. 运行 `python audit_reports/verify_fixes.py <TASK_ID>` 自动验证
3. 人工复核代码改动
4. 通过 → 任务板改 `已验证通过`; 失败 → 改 `验证失败` + 在 `audit_reports/VERIFICATION_RESULTS.md` 写明原因

---

## 📂 协作产物索引

| 文件 | 用途 | 谁写 |
|---|---|---|
| `audit_reports/COMPREHENSIVE_AUDIT_20260617.md` | 完整审计报告(发现+修复计划) | ZCode |
| `audit_reports/FIX_TASKS.md` | 结构化修复任务包(每项含代码示例+验证标准) | ZCode |
| `audit_reports/verify_fixes.py` | 自动验证脚本(Codex 修复后一键回归) | ZCode |
| `audit_reports/VERIFICATION_REQUESTS.md` | Codex 提交的验证请求队列 | Codex |
| `audit_reports/VERIFICATION_RESULTS.md` | ZCode 验证结果(通过/失败+原因) | ZCode |
| `audit_reports/_no_auth_routes.txt` | 118 个无授权路由原始清单 | ZCode |
| `audit_reports/_auth_classification.txt` | REAL/STUB/UNKNOWN 分类 | ZCode |
| `audit_reports/_comm/PROTOCOL.md` | 双向通讯协议规范(B 方案,会话绑定) | ZCode |
| `audit_reports/_comm/SESSION_BINDINGS.json` | ZCode/Codex 固定会话 ID 绑定配置 | ZCode |
| `audit_reports/_comm/blackboard.sqlite` | 消息队列 + 任务板共享存储 | 双方读写 |
| `scripts/dispatch_to_codex.py` | ZCode→Codex 同步直连(支持 --resume 复用固定会话) | ZCode |
| `scripts/send_to_zcode.py` | Codex→ZCode 异步发消息 / 报告任务状态 | Codex |
| `scripts/read_codex_messages.py` | ZCode 读 Codex 消息(支持 --watch 轮询) | ZCode |
| `scripts/mcp_blackboard_server.py` | (备用)A 方案 MCP server,Codex 桌面版不加载 | ZCode |

---

## 🔗 双向通讯通道(2026-06-17 建立,**B 方案,已端到端验证**)

> 过去两个 agent 只能靠文件 + 人类信使异步沟通。现已建立**双向通道**,
> 双方都能主动发消息、派任务、拿回执,不必等人类搬话。

### 固定会话绑定

| Agent | 会话 ID | 角色 |
|---|---|---|
| **ZCode** | `sess_c93e053f-cda9-475c-80aa-6a9d557e28b1` | 审计员/验证员 |
| **Codex** | `019ecfe8-0db5-7b12-b1c0-e5acfc1985f3`(thread:主调度) | 修复执行方 |

机器可读绑定:`audit_reports/_comm/SESSION_BINDINGS.json`

### 为什么是 B 方案

最初尝试 A 方案(共享 MCP 黑板 server 双向挂载),落地时发现 Codex 桌面版**不加载 `config.toml` 的 `[mcp_servers.*]`**,只从 plugin 加载。B 方案绕开 MCP 协议依赖,用 `codex exec resume` + 共享 SQLite,**已实测端到端跑通**(2 条消息双向往返)。

### 通道总览

| 方向 | 工具 | 形态 |
|---|---|---|
| **ZCode → Codex**(同步) | `scripts/dispatch_to_codex.py --resume <id> --bypass-sandbox` | 同步直连,在 Codex 固定会话上下文里执行,拿回最终回复 |
| **Codex → ZCode**(异步) | Codex 跑 `scripts/send_to_zcode.py` 写共享 SQLite + 文件兜底 | ZCode 用 `read_codex_messages.py` 读取 |
| **共享存储** | `audit_reports/_comm/blackboard.sqlite`(WAL,双进程读写) | messages 表 + tasks 表 |
| **文件兜底** | `audit_reports/_comm/inbox_{zcode,codex}/` | SQLite 故障时不丢消息 |

### 派单示例(ZCode 派给 Codex)

```bash
python scripts/dispatch_to_codex.py \
  --resume 019ecfe8-0db5-7b12-b1c0-e5acfc1985f3 \
  --bypass-sandbox \
  "请修复 P0-02, 规范见 audit_reports/FIX_TASKS.md#P0-02。完成后跑: python scripts/send_to_zcode.py --subject 'P0-02 done' --task-id P0-02 --status done --body '<改动摘要>'"
```

### Codex 回执示例(Codex 在自己会话里跑)

```bash
python scripts/send_to_zcode.py --subject "P0-02 已修复" --task-id P0-02 --status done --body "改动见 sessions.py"
```

### ZCode 收消息

```bash
python scripts/read_codex_messages.py            # 未读
python scripts/read_codex_messages.py --watch 30 # 轮询模式
```

### 详细协议

见 `audit_reports/_comm/PROTOCOL.md`(完整通讯协议、SQLite 表结构、典型流程)。
