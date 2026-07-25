# X-Agent Hooks 指南

本指南介绍 X-Agent 的 Hooks（钩子）系统：如何配置、编写和管理在智能体执行关键节点拦截、放行、修改或要求审批的钩子。

## 目录

- [核心概念](#核心概念)
- [Hooks 与 EventBus 的区别](#hooks-与-eventbus-的区别)
- [事件类型](#事件类型)
- [动作语义](#动作语义)
- [聚合策略](#聚合策略)
- [配置文件格式](#配置文件格式)
- [钩子类型](#钩子类型)
  - [command 钩子](#command-钩子)
  - [python 钩子](#python-钩子)
- [CLI 命令](#cli-命令)
- [典型场景](#典型场景)
- [执行流程与集成点](#执行流程与集成点)
- [最佳实践](#最佳实践)
- [故障排查](#故障排查)

---

## 核心概念

Hooks 是 X-Agent 的**控制平面（control plane）**：在智能体执行的关键节点上，钩子可以拦截事件并决定后续行为——放行、拒绝、要求人工审批，或在执行前后修改数据。

一个钩子接收一个不可变的 `HookContext`（描述当前事件），返回一个 `HookDecision`（裁决）。`HookManager` 负责把同一事件上的多个钩子裁决聚合成最终的 `HookResult`，并应用到智能体的工具执行咽喉点（`backend/app/core/tools.py::ToolRegistry.execute`）和生命周期节点（`backend/app/core/agent/loop.py::AgentLoop.run`）。

核心数据类型（定义于 `backend/app/core/hooks/types.py`）：

| 类型 | 作用 |
| --- | --- |
| `HookEvent` | 钩子可触发的事件枚举 |
| `HookAction` | 钩子裁决：allow / deny / ask / modify |
| `HookContext` | 传给钩子的不可变事件载荷（冻结的 dataclass） |
| `HookDecision` | 单个钩子返回的裁决 |
| `HookResult` | 聚合后的最终结果 |
| `Hook` | 钩子需实现的协议（async 可调用 + name/events/priority） |

---

## Hooks 与 EventBus 的区别

X-Agent 已有一个 `EventBus`（`backend/app/core/event_bus.py`）。理解两者的区别很重要：

- **EventBus 只做观察（observation only）**：发布-订阅模式，订阅者**不能**阻断或修改执行流。它用于审计、指标、日志等旁路观测。
- **Hooks 做控制（control）**：钩子可以 `deny`（阻断）、`ask`（要求审批）、`modify`（改写输入/输出）。

Hooks 是一个**全新的拦截层**，而不是 EventBus 的包装。为了兼容现有观测能力，`HookManager` 在裁决之后会尽力（best-effort）向 EventBus 发布一条可观测事件——但这条发布**永不影响控制决策、永不抛错**。

---

## 事件类型

`HookEvent` 枚举（字符串值即配置中 `events` 数组里使用的值）：

| 枚举 | 配置值 | 触发时机 |
| --- | --- | --- |
| `PRE_TOOL_USE` | `pre_tool_use` | 工具执行前，包裹 `ToolRegistry.execute` 中 `tool.handler` 调用之前 |
| `POST_TOOL_USE` | `post_tool_use` | 工具执行成功后，`tool.handler` 调用之后 |
| `AGENT_START` | `agent_start` | `AgentLoop.run` 启动时 |
| `AGENT_STOP` | `agent_stop` | `AgentLoop` 结束（`_finalize_execution`）时 |
| `USER_PROMPT_SUBMIT` | `user_prompt_submit` | 用户任务/提示进入循环时 |

> 说明：`AGENT_STOP` 在运行结束时触发，仅作通知用途，不再具有拒绝语义（此时执行已完成）。

---

## 动作语义

钩子通过返回 `HookDecision` 表达裁决，`HookAction` 有四种：

| 动作 | 配置/返回值 | 含义 |
| --- | --- | --- |
| `ALLOW` | `allow` | 放行，不做改动。 |
| `DENY` | `deny` | 阻断当前动作；管理器立即短路，剩余钩子不再执行。 |
| `ASK` | `ask` | 要求人工审批后才能继续（由集成层路由到现有的 `ApprovalStore`）。 |
| `MODIFY` | `modify` | 继续执行，但用 `modified_input`（PRE）或 `modified_output`（POST）替换原始载荷。 |

`HookDecision` 提供了工厂方法方便构造：`HookDecision.allow()`、`.deny(reason)`、`.ask(reason)`、`.modify_input(arguments)`、`.modify_output(result)`。

聚合后的 `HookResult` 提供三个便捷属性：

- `allowed` —— 最终动作为 ALLOW 或 MODIFY 时为 True（可继续执行）。
- `denied` —— 最终动作为 DENY 时为 True（必须阻断）。
- `needs_approval` —— 最终动作为 ASK 时为 True（需先审批）。

---

## 聚合策略

当一个事件上注册了多个钩子时，`HookManager.trigger` 按 `priority` **升序**（数字小的先跑）依次执行，并以**失败关闭（fail-closed）+ 短路**的方式聚合：

1. **第一个 DENY 立即胜出**——后续钩子不再执行（短路）。
2. 否则 **ASK 具有粘性**——任意一个钩子返回 ASK，最终结果即为 ASK。
3. **MODIFY 会链式叠加**——每个钩子改写的载荷会作为下一个钩子的输入，因此多个修改可以组合。
4. 没有 DENY/ASK 时，结果为 ALLOW（若有钩子改写过载荷则为 MODIFY）。

> 容错设计：单个钩子**抛出异常**时被视为 ALLOW（错误会记入日志，但不致命）。这样一个有 bug 的观察型钩子不会把智能体卡死——阻断必须是**显式的 DENY**。

---

## 配置文件格式

钩子配置位于项目本地的 `.xagent/hooks.json`（该目录由 CLI `xagent init project` 创建）。常量 `DEFAULT_CONFIG_RELPATH = ".xagent/hooks.json"`。

顶层是一个对象，含 `hooks` 数组，每个元素是一条 `HookDefinition`：

```json
{
  "hooks": [
    {
      "name": "block-prod-writes",
      "type": "command",
      "events": ["pre_tool_use"],
      "command": ["python", ".xagent/hooks/guard.py"],
      "tool_matcher": "write_file|apply_text_patch",
      "priority": 10,
      "timeout_seconds": 5.0,
      "enabled": true
    },
    {
      "name": "audit-logger",
      "type": "python",
      "events": ["post_tool_use"],
      "target": "mypkg.hooks:AuditHook",
      "priority": 50,
      "enabled": true
    }
  ]
}
```

字段说明（`HookDefinition`，定义于 `backend/app/core/hooks/config.py`）：

| 字段 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `name` | 是 | — | 唯一标识，用于日志和审计记录。 |
| `type` | 是 | — | `"command"`（子进程）或 `"python"`（进程内导入）。 |
| `events` | 是 | `[]` | 订阅的事件值数组（见[事件类型](#事件类型)）。 |
| `command` | command 类型必填 | `null` | argv 数组（**绝不是** shell 字符串，避免注入）。 |
| `target` | python 类型必填 | `null` | 点分导入路径 `"module:attr"`。 |
| `tool_matcher` | 否 | `null` | 正则，匹配 `tool_name`；设置后钩子只对匹配的工具触发。 |
| `priority` | 否 | `100` | 数字越小越先执行。 |
| `timeout_seconds` | 否 | `5.0` | command 钩子的最大运行时长，必须 > 0。 |
| `enabled` | 否 | `true` | 为 false 时加载阶段直接跳过。 |

校验规则（`HookDefinition.validate` 与 `HooksConfig.validate`）：缺 `name`、`type` 非法、未声明 `events`、无可解析的事件、command 类型缺 `command`、python 类型缺 `target`、`timeout_seconds <= 0`、**钩子重名**等都会报错。

---

## 钩子类型

执行器（`backend/app/core/hooks/executors.py`）把声明式配置转成可运行的 `Hook` 对象。两种类型都支持可选的 `tool_matcher` 正则——对工具事件，若 `tool_name` 不匹配则短路为 ALLOW。

### command 钩子

通过 `asyncio` 子进程运行外部程序。`HookContext` 以 JSON 形式写入 stdin；程序向 stdout 写出 JSON 裁决并退出。

stdout JSON 至少包含 `action` 键（`"allow"` / `"deny"` / `"ask"` / `"modify"`），可选 `reason`、`modified_input`、`modified_output`。

退出码语义：

- **0**：解析 stdout JSON 得到裁决。
- **非 0**：视为 ALLOW（fail-open，记警告）。
- **超时**：视为 ALLOW（记警告）。
- **无法启动 / stdout 非合法 JSON / 未知 action**：均视为 ALLOW。

一个最简单的守卫脚本（`.xagent/hooks/guard.py`）示例：

```python
#!/usr/bin/env python3
"""阻止对生产路径的写操作。"""
import json
import sys

ctx = json.load(sys.stdin)
path = ctx.get("arguments", {}).get("path", "")

if path.startswith("/prod/"):
    print(json.dumps({"action": "deny", "reason": f"禁止写入生产路径: {path}"}))
else:
    print(json.dumps({"action": "allow"}))
```

### python 钩子

进程内导入点分路径 `"module:attr"` 并包装解析出的对象。支持四种目标形态：

1. 一个 `Hook` **实例**（直接使用）。
2. 一个实现了 `Hook` 的**类**（无参实例化）。
3. 一个**工厂** `() -> Hook`（加载时调用一次）。
4. 一个裸 async 可调用 `(HookContext) -> HookDecision`（包装使用）。

> 实现注意：类的判断**先于**实例判断，因为 `runtime_checkable` 协议的 `isinstance()` 也会匹配类对象本身。

一个审计钩子类示例：

```python
from backend.app.core.hooks.types import HookContext, HookDecision, HookEvent

class AuditHook:
    name = "audit-logger"
    events = {HookEvent.POST_TOOL_USE}
    priority = 50

    async def __call__(self, context: HookContext) -> HookDecision:
        # 记录工具执行，但不改变控制流
        log_line = f"tool={context.tool_name} trace={context.trace_id}"
        # ... 写日志 / 上报指标 ...
        return HookDecision.allow(hook_name=self.name)
```

对应配置中 `"target": "myproject.hooks:AuditHook"` 即可（这里指向类，执行器会自动实例化）。

---

## CLI 命令

CLI 命令组 `xagent hooks`（实现于 `cli/commands/hooks_cmd.py`）直接读取本地 `.xagent/hooks.json`，不经过后端 HTTP——因为钩子是项目本地配置，而非后端状态。

所有子命令都支持 `--path / -p` 指定项目目录（默认当前目录）。

### init —— 初始化配置

```bash
xagent hooks init            # 在 .xagent/hooks.json 写入示例配置
xagent hooks init --force    # 覆盖已存在的配置
```

生成的示例钩子默认 `"enabled": false`，编辑后把要启用的改为 `true`。

### list —— 列出钩子

```bash
xagent hooks list            # 仅列出已启用的钩子
xagent hooks list --all      # 包含已禁用的钩子
```

以表格展示每个钩子的 Name / Type / Events / Priority / Enabled。

### validate —— 校验配置

```bash
xagent hooks validate
```

检查语法错误、缺失必填字段、非法事件名、重名等；通过时打印钩子数量与启用数量，失败时逐条列出错误并以退出码 1 结束。

### show —— 查看单个钩子

```bash
xagent hooks show block-prod-writes
```

展示钩子的完整配置：类型、事件、优先级、启用状态、命令/目标、超时、tool_matcher，以及该钩子的校验状态。

---

## 典型场景

### 场景一：阻止危险工具调用

用 command 钩子在 `pre_tool_use` 上拦截危险路径写入：

```json
{
  "name": "block-prod-writes",
  "type": "command",
  "events": ["pre_tool_use"],
  "command": ["python", ".xagent/hooks/guard.py"],
  "tool_matcher": "write_file|apply_text_patch|delete_file",
  "priority": 10,
  "enabled": true
}
```

### 场景二：高风险操作要求人工审批

钩子返回 `ask`，集成层会创建审批请求（路由到 `ApprovalStore`），执行被挂起直到审批通过：

```python
async def __call__(self, context):
    if context.risk_level == "high":
        return HookDecision.ask(
            reason="高风险操作需人工确认", hook_name=self.name
        )
    return HookDecision.allow(hook_name=self.name)
```

### 场景三：在执行前注入/改写参数

`pre_tool_use` 上返回 `modify_input`，用改写后的参数替换原始参数：

```python
async def __call__(self, context):
    args = dict(context.arguments)
    args.setdefault("timeout", 30)   # 强制默认超时
    return HookDecision.modify_input(args, hook_name=self.name)
```

### 场景四：脱敏工具输出

`post_tool_use` 上返回 `modify_output`，在结果回到智能体前做脱敏。

### 场景五：纯审计（不改变控制流）

python 钩子订阅 `post_tool_use` 或 `agent_stop`，记录后始终返回 `allow`（见上文 `AuditHook`）。

---

## 执行流程与集成点

钩子在两处被织入，对未注册钩子的情况是**完美无操作（no-op）、完全向后兼容**：

**工具咽喉点**（`backend/app/core/tools.py::ToolRegistry.execute`）：

```
查找工具 → 策略评估 → 既有审批 → 参数校验
        → [PRE_TOOL_USE 钩子]
        → tool.handler(**arguments)
        → [POST_TOOL_USE 钩子]
        → ToolCallRecord
```

- PRE 阶段：DENY → 直接生成失败记录；ASK → 创建工具审批并以含 `approval_id` 的失败记录返回；MODIFY → 原地替换 `arguments`。
- POST 阶段：MODIFY → 改写输出。

**生命周期点**（`backend/app/core/agent/loop.py::AgentLoop`）：

- `run()` 开头依次触发 `AGENT_START` 与 `USER_PROMPT_SUBMIT`；若 DENY，提前返回 `AgentRunResponse(status=FAILED, error=拒绝原因)`。
- `_finalize_execution` 末尾尽力触发 `AGENT_STOP`（运行已结束，无拒绝语义）。

**注册时机无关性**：`HookManager` 是可变的全局单例（`get_hook_manager()` / `set_hook_manager()`），`ToolRegistry` 持有其引用。即使工具注册表先于钩子注册而构建，启动时注册的钩子仍会触发。`backend/app/main.py` 的 `startup_event()` 会加载 `.xagent/hooks.json`、校验、并调用 `register_hooks_from_config(get_hook_manager(), hooks_config)`（包在 fail-open 的 try/except 中）。

---

## 最佳实践

- **优先用 `tool_matcher` 缩小触发范围**，避免每次工具调用都唤起子进程，降低开销。
- **command 钩子保持快速**并设合理 `timeout_seconds`；超时会被 fail-open 放行。
- **阻断必须显式 DENY**——不要依赖抛异常来阻断，异常会被当作 ALLOW。
- **priority 留出间隔**（如 10、50、100），方便后续插入钩子而无需重排。
- **观察型钩子（审计/指标）始终返回 ALLOW**，把控制权留给专门的守卫钩子。
- **改配置后先 `xagent hooks validate`** 再启用，避免重名或非法事件导致整条配置加载异常。
- **command 钩子用 argv 数组**，绝不用 shell 字符串拼接，防止命令注入。

---

## 故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 钩子没触发 | `enabled: false`，或 `tool_matcher` 不匹配，或事件值拼写错误 | `xagent hooks show <name>` 检查；用 `xagent hooks validate` 校验事件名。 |
| `xagent hooks list` 为空 | 只列出启用项 | 加 `--all` 查看被禁用的钩子。 |
| 配置整体未加载 | JSON 语法错误或重名 | 看启动日志 `Failed to load hooks configuration`；运行 `xagent hooks validate`。 |
| command 钩子总是放行 | 退出码非 0、超时、stdout 非合法 JSON、或未知 action | 检查脚本 stdout 是否为 `{"action": ...}` JSON；查看日志中的 warning。 |
| python 钩子加载失败 | `target` 非 `"module:attr"` 形式，或导入失败 | 确认模块可被后端导入；查看 `Failed to build hook` 日志（加载阶段 fail-open，会跳过该钩子）。 |
| 钩子报错但智能体继续运行 | 设计如此：抛异常被当作 ALLOW | 这是容错行为；要阻断请显式返回 DENY。 |

---

## 相关文件

- `backend/app/core/hooks/types.py` —— 核心类型定义
- `backend/app/core/hooks/manager.py` —— HookManager 注册与分发
- `backend/app/core/hooks/config.py` —— 配置加载与校验
- `backend/app/core/hooks/executors.py` —— command / python 执行器
- `cli/commands/hooks_cmd.py` —— `xagent hooks` CLI 命令
- `.xagent/hooks.json` —— 项目本地钩子配置
