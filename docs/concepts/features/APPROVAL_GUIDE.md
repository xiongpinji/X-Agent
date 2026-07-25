# X-Agent 审批系统指南

本指南介绍 X-Agent 的审批系统（Approval System）：当工具执行需要人工确认时，如何创建、查看、决策和执行审批请求。

## 目录

- [核心概念](#核心概念)
- [审批状态机](#审批状态机)
- [审批触发方式](#审批触发方式)
- [数据模型](#数据模型)
- [API 端点](#api-端点)
- [CLI 命令](#cli-命令)
- [典型场景](#典型场景)
- [与 Hooks 的集成](#与-hooks-的集成)
- [最佳实践](#最佳实践)
- [故障排查](#故障排查)

---

## 核心概念

审批系统是 X-Agent 的**人机协作层（human-in-the-loop layer）**：当智能体尝试执行高风险工具或钩子返回 `ASK` 时，系统会创建一条审批请求，暂停执行，等待人工决策后再继续。

核心组件：

| 组件 | 位置 | 作用 |
| --- | --- | --- |
| `ApprovalStore` | `backend/app/core/approvals.py` | 内存+JSON 持久化的审批存储 |
| `ApprovalRequestRecord` | 同上 | 审批请求的 Pydantic 模型 |
| API 路由 | `backend/app/api/approvals.py` | `/api/v1/approvals` REST 端点 |
| CLI 命令 | `cli/commands/approvals_cmd.py` | `xagent approvals` 命令组 |

---

## 审批状态机

审批请求的生命周期由 `ApprovalStatus` 枚举描述：

```
                ┌──────────┐
                │ PENDING  │  ← 创建时的初始状态
                └────┬─────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    ┌─────────┐ ┌──────────┐ (超时/取消)
    │APPROVED │ │ REJECTED │
    └────┬────┘ └──────────┘
         │
         ▼
    ┌──────────┐
    │ EXECUTED │  ← 工具实际执行后
    └──────────┘
```

| 状态 | 含义 |
| --- | --- |
| `PENDING` | 等待人工决策 |
| `APPROVED` | 已批准，可执行 |
| `REJECTED` | 已拒绝，不可执行 |
| `EXECUTED` | 已批准且工具已执行完成 |

---

## 审批触发方式

审批请求可通过两种途径创建：

### 1. 策略引擎（ToolPolicyEngine）

当工具的风险等级超过当前上下文的权限阈值时，`ToolPolicyEngine.evaluate()` 返回 `requires_approval=True`，`ToolRegistry.execute()` 会调用 `ApprovalStore.create_tool_approval()` 创建审批。

```python
verdict = self._policy.evaluate(context, tool.name, tool.risk_level)
if not verdict.allowed and verdict.requires_approval:
    approval = self._approval_store.create_tool_approval(...)
```

### 2. Hooks 返回 ASK

当 `pre_tool_use` 钩子返回 `HookDecision.ask(reason="...")`，`ToolRegistry._run_pre_tool_hooks()` 会创建审批请求：

```python
if result.needs_approval:
    approval = self._approval_store.create_tool_approval(
        context=context,
        tool_name=tool.name,
        risk_level=tool.risk_level,
        reason=result.reason or "approval required by hook",
        arguments_preview=...,
        arguments=arguments,
    )
```

两种方式创建的审批请求结构相同，后续的决策和执行流程也一致。

---

## 数据模型

`ApprovalRequestRecord`（定义于 `backend/app/core/approvals.py`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | str | UUID，唯一标识 |
| `tenant_id` | str | 租户 ID |
| `actor_id` | str | 发起请求的用户 ID |
| `trace_id` | str | 关联的追踪 ID |
| `resource_type` | str | 资源类型，通常为 `"tool"` |
| `resource_id` | str | 资源 ID，即工具名 |
| `action` | str | 动作，通常为 `"tool.execute"` |
| `risk_level` | RiskLevel | 风险等级（low/medium/high/critical） |
| `status` | ApprovalStatus | 当前状态 |
| `reason` | str | 创建审批的原因 |
| `arguments_preview` | dict | 参数预览（脱敏后） |
| `arguments` | dict | 完整参数（用于执行） |
| `decided_by` | str \| None | 决策者 ID |
| `decided_at` | datetime \| None | 决策时间 |
| `decision_reason` | str \| None | 决策理由 |
| `executed_by` | str \| None | 执行者 ID |
| `executed_at` | datetime \| None | 执行时间 |
| `execution_trace_id` | str \| None | 执行时的追踪 ID |
| `linked_policy_trace_id` | str \| None | 关联的策略追踪 ID |
| `created_at` | datetime | 创建时间 |

---

## API 端点

所有审批端点挂载在 `/api/v1/approvals` 前缀下（定义于 `backend/app/api/approvals.py`），并统一要求调用方持有 `workflow:control` 权限范围（通过 `enforce_scope` 校验）。

| 方法 | 路径 | 作用 | 请求体 | 响应模型 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/approvals` | 列出审批请求 | — | `list[ApprovalRequestRecord]` |
| GET | `/api/v1/approvals/{id}` | 获取单条审批详情 | — | `ApprovalRequestRecord` |
| GET | `/api/v1/approvals/{id}/correlation` | 获取审批的追踪关联与恢复上下文 | — | `dict` |
| POST | `/api/v1/approvals/{id}/approve` | 批准请求 | `ApprovalDecisionRequest` | `ApprovalRequestRecord` |
| POST | `/api/v1/approvals/{id}/reject` | 拒绝请求 | `ApprovalDecisionRequest` | `ApprovalRequestRecord` |
| POST | `/api/v1/approvals/{id}/execute` | 执行已批准的工具 | — | `ToolCallRecord` |

### 查询参数（list）

| 参数 | 类型 | 默认 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `limit` | int | 50 | 1–200 | 返回的最大记录数 |
| `status` | ApprovalStatus | — | — | 按状态过滤（pending/approved/rejected/executed） |
| `tenant_id` | str | — | — | 按租户过滤 |

### 决策请求体（ApprovalDecisionRequest）

`approve` 和 `reject` 端点接受相同的决策请求体：

```json
{
  "decided_by": "alice",
  "reason": "verified safe to run"
}
```

### 执行行为

`POST /{id}/execute` 会做几件事：

1. 校验审批记录存在，并检查租户一致性（`principal.tenant_id` 必须匹配 `record.tenant_id`，否则返回 403）。
2. 用审批记录中保存的 `arguments` 重建 `RunContext`，调用 `agent.tools.execute_approved()` 实际执行工具。
3. 调用 `approval_store.mark_executed()` 将状态推进到 `EXECUTED`，并记录执行者与执行追踪 ID。
4. 返回工具调用结果 `ToolCallRecord`（包含 `success`、`latency_ms`、`error` 等字段）。

### 审计

`approve` / `reject` / `execute` 三个写操作都会通过 `AuditStore.record()` 写入审计事件（`approval.approve` / `approval.reject` / `approval.execute`），便于事后追溯谁在何时做了什么决策。

---

## CLI 命令

CLI 命令组 `xagent approvals`（定义于 `cli/commands/approvals_cmd.py`）封装了上述端点。

> **注意**：审批是后端状态，CLI 的审批命令仅支持 **HTTP 模式**。在 local 模式下调用会抛出 `NotImplementedError` 并提示切换模式。

| 命令 | 作用 | 主要选项 |
| --- | --- | --- |
| `xagent approvals list` | 列出审批请求 | `--status/-s`、`--tenant/-t`、`--limit/-n` |
| `xagent approvals show <id>` | 查看单条审批详情 | — |
| `xagent approvals approve <id>` | 批准请求 | `--by/-b`、`--reason/-r` |
| `xagent approvals reject <id>` | 拒绝请求 | `--by/-b`、`--reason/-r` |
| `xagent approvals execute <id>` | 执行已批准的工具 | — |

### 示例

列出所有待决策的审批：

```bash
xagent approvals list --status pending
```

查看某条审批的完整信息：

```bash
xagent approvals show 7f3a1c2e-...
```

批准并执行：

```bash
xagent approvals approve 7f3a1c2e-... --by alice --reason "verified safe"
xagent approvals execute 7f3a1c2e-...
```

拒绝一条风险过高的请求：

```bash
xagent approvals reject 7f3a1c2e-... --by alice --reason "too risky"
```

> CLI 全局选项 `--output json` 可让任意命令以 JSON 格式输出，便于脚本化处理。

---

## 典型场景

### 场景 A：策略阈值触发审批

1. 智能体调用一个 `high` 风险工具（如 `shell.execute`），当前上下文权限阈值为 `medium`。
2. `ToolPolicyEngine.evaluate()` 返回 `requires_approval=True`，`ToolRegistry.execute()` 创建审批并暂停执行。
3. 运维通过 `xagent approvals list --status pending` 发现待决策项。
4. 用 `xagent approvals show <id>` 检查参数预览，确认无误后 `approve`，再 `execute`。

### 场景 B：Hook 主动要求审批

1. 自定义 `pre_tool_use` 钩子检测到敏感目标（如生产数据库），返回 `HookDecision.ask(reason="prod DB write")`。
2. `ToolRegistry._run_pre_tool_hooks()` 据此创建审批，`reason` 即钩子给出的理由。
3. 后续决策与执行流程与场景 A 完全一致。

### 场景 C：拒绝后的处理

被 `reject` 的审批进入终态，不会再被执行。智能体应将拒绝视为该工具调用失败，按既定的错误恢复路径继续（例如换用低风险替代方案或向用户回报）。

---

## 与 Hooks 的集成

审批系统与 Hooks 的衔接点在 `ToolRegistry._run_pre_tool_hooks()`：

```
pre_tool_use 钩子
      │
      ├─ ALLOW ─────────────► 正常执行工具
      │
      ├─ DENY  ─────────────► 阻断，工具不执行
      │
      └─ ASK ──► 创建审批请求 ──► PENDING ──► 人工决策
                                              ├─ APPROVED ──► execute ──► EXECUTED
                                              └─ REJECTED ──► 终止
```

关键点：

- 钩子返回 `ASK` 时，`HookResult.needs_approval` 为 `True`，`reason` 会原样写入审批记录，作为人工决策时的判断依据。
- 钩子无需感知审批存储的存在；它只负责表达"需要人工确认"的意图，创建审批的职责由 `ToolRegistry` 承担。
- 策略引擎与钩子是两条独立的触发路径，但创建出的审批记录结构一致，下游处理统一。

> 关于 Hooks 的完整说明（钩子类型、决策语义、注册方式），参见 `docs/HOOKS_GUIDE.md`。

---

## 最佳实践

- **决策前务必查看参数预览**：用 `xagent approvals show <id>` 确认 `arguments_preview`，避免盲批高风险操作。
- **始终填写决策理由**：`--reason` 会进入审计日志，是事后追溯的关键证据。
- **approve 与 execute 分离**：批准只是授权，执行才真正运行工具。两步分离让你有机会在执行前再做一次环境检查。
- **关注租户边界**：`execute` 会校验租户一致性，跨租户执行会被拒绝（403）。在多租户场景下确认决策者归属正确的租户。
- **用状态过滤聚焦**：日常巡检用 `--status pending` 只看待办，避免被历史记录淹没。
- **脚本化用 JSON 输出**：自动化流程中加 `--output json`，结构化解析比正则匹配文本可靠得多。

---

## 故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| CLI 报 `NotImplementedError` | 当前处于 local 模式 | 审批命令仅支持 HTTP 模式，用 `--mode http` 或设置 `XAGENT_MODE=http` |
| `Approval request not found`（404） | 审批 ID 错误，或后端重启后内存状态丢失 | 核对 ID；确认 `ApprovalStore` 的 JSON 持久化路径已正确配置 |
| `execute` 返回 403 | 决策者租户与审批记录租户不一致 | 用归属正确租户的身份执行，或检查 `principal.tenant_id` |
| `approve` 后无法 `execute` | 请求未处于 `approved` 状态 | 先确认 `show` 中 `status` 为 approved；已 rejected/executed 的请求不可再执行 |
| 列表为空 | 过滤条件过严，或确实没有审批 | 去掉 `--status` / `--tenant` 过滤再查 |
| 权限不足（403/AUTHORIZATION_FAILED） | 缺少 `workflow:control` 范围 | 使用具备该权限范围的 API Key |

---

## 参考

- 审批存储实现：`backend/app/core/approvals.py`
- API 路由：`backend/app/api/approvals.py`
- CLI 命令：`cli/commands/approvals_cmd.py`
- Hooks 指南：`docs/HOOKS_GUIDE.md`
