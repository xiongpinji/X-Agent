# AGENTS.md — 多 Agent 协作协调黑板

> **本文件是 Codex(总调度 `019ecfe8`)与 ZCode(会话 `sess_c93e053f`)的共享协作黑板。**
> 任何一方开始/完成任务前,必须先读本文件更新自己的状态,完成后回写进度。
> 协作介质:① 文件系统(本文件 + `audit_reports/`);② **双向实时通道**(MCP 黑板 + `codex exec` 直连,见文末「🔗 双向通讯通道」)。

**最后更新**: 2026-06-17 (ZCode)
**当前协作阶段**: 安全漏洞修复(基于 `audit_reports/COMPREHENSIVE_AUDIT_20260617.md`)

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
| P0-01 | enterprise.py 14 端点加授权 | `backend/app/api/enterprise.py` | 已修复待验证(Codex 019ecfe8) | 见 `audit_reports/FIX_TASKS.md#P0-01` |
| P0-02 | sessions.py 6 端点强制 principal.tenant_id | `backend/app/api/sessions.py` | 进行中(Codex 019ecfe8) | 见 `audit_reports/FIX_TASKS.md#P0-02` |
| P0-03 | skills_api.py 4 端点强制 principal | `backend/app/api/skills_api.py` | 待领取 | 见 `audit_reports/FIX_TASKS.md#P0-03` |
| P0-04 | issue_to_pr.py execute 端点加授权 | `backend/app/api/issue_to_pr.py:49` | 待领取 | 见 `audit_reports/FIX_TASKS.md#P0-04` |
| P0-05 | 核实 reset_password 令牌验证 | `backend/app/api/auth.py:431` | ✅ 已验证通过(ZCode) | **非漏洞**:reset_password 有完整双流程+token校验,见 `VERIFICATION_RESULTS.md` |
| P0-06 | main.py:580 WARNING 改 raise | `backend/app/main.py:580` | 待领取 | 见 `audit_reports/FIX_TASKS.md#P0-06` |

### P1 — 一周内

| ID | 任务 | 文件 | 状态 |
|---|---|---|---|
| P1-01 | 撤销 4 个被跟踪的 .env 文件 | `.env.{development,production,test,performance}` | 待领取 |
| P1-02 | 加 pre-commit gitleaks 钩子 | `.pre-commit-config.yaml` | 待领取 |
| P1-03 | 审计 35 个 UNKNOWN 未授权路由 | `enterprise_audit/migration/sso/i18n/...` | 待领取 |
| P1-04 | saml_sso.py 用 defusedxml + 真签名验证 | `backend/app/core/saml_sso.py` | 待领取 |
| P1-05 | 4 个无 timeout 的 HTTP 请求加 timeout | `plugin_crawler.py` 等 | 待领取 |

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
| `audit_reports/_comm/PROTOCOL.md` | 双向通讯协议规范(MCP+文件兜底) | ZCode |
| `scripts/mcp_blackboard_server.py` | 共享 MCP 黑板 server(双向消息队列) | ZCode |
| `scripts/dispatch_to_codex.py` | ZCode→Codex 同步直连封装(`codex exec`) | ZCode |
| `audit_reports/_comm/blackboard.sqlite` | 消息队列持久化存储 | 双方读写 |

---

## 🔗 双向通讯通道(2026-06-17 建立)

> 过去两个 agent 只能靠文件 + 人类信使异步沟通。现已建立**双向实时通道**,
> 双方都能主动发消息、派任务、拿回执,不必等人类搬话。

### 通道总览

| 通道 | 方向 | 形态 | 何时用 |
|---|---|---|---|
| **MCP 黑板**(主) | 双向对称 | 共享 MCP server,双方各自挂载,读写同一 SQLite 队列 | 默认双向通讯。派单、回执、问询、状态同步 |
| **`codex exec` 直连** | ZCode→Codex | ZCode 用 Bash 同步调起 Codex,即时拿回结果 | 需要Codex**立即执行并返回**时(如现场验证) |
| **文件收件箱**(兜底) | 双向异步 | `audit_reports/_comm/inbox_{zcode,codex}/` | MCP server 未加载(会话未重启)时兜底,保证不丢消息 |

### MCP 黑板工具(双方均可调用)

- `post_message(sender, recipient, subject, body)` —— 投递消息,recipient ∈ {zcode, codex, broadcast}
- `read_inbox(agent, since_id?, limit?)` —— 读自己收件箱;不带 since_id 返回未读并标记已读
- `create_task(task_id, created_by, summary, detail?)` —— 任务板上建任务
- `claim_task(task_id, claimed_by)` —— 认领任务 → in_progress
- `report_done(task_id, status, summary, by)` —— 报告 done/failed/blocked
- `list_tasks(status?)` —— 列出任务板

### ZCode 同步调用 Codex

```bash
# ZCode 在会话内用 Bash 执行:
venv\Scripts\python.exe scripts\dispatch_to_codex.py --timeout 300 "请修复 P0-02, 规范见 audit_reports/FIX_TASKS.md#P0-02"
# Codex 的最终回复会打印到 stdout, 同时落盘 audit_reports/_comm/_codex_last.txt
```

### 生效条件 ⚠️

MCP 黑板 server 已挂载到 `.mcp.json`(ZCode)和 `.codex/config.toml`(Codex),
但 **双方都需重启各自会话** 才能加载新 MCP server。重启前只能用 `codex exec` 直连 + 文件兜底。

### 详细协议

见 `audit_reports/_comm/PROTOCOL.md`(消息格式、调用约定、文件兜底确认机制)。
