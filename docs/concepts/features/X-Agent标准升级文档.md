# X-Agent 标准升级文档

版本：v1.0
日期：2026-05-26
范围：X-Agent 原创内核计划 / 根目录规范升级方案

## 1. 文档目标

本文档定义 X-Agent 从“统一控制台型平台”升级为“可治理、可恢复、可扩展的 Agent 操作系统”的标准路线。重点对标 Claude Code 的成熟内核能力，并结合 X-Agent 现有的前后端控制台架构，形成可执行的升级标准。

本次升级的核心目标：

1. 统一 agent 运行、工具执行、记忆、审计、恢复的协议。
2. 建立可复用的提示工程体系，让提示词成为平台级能力，而不是散落在各个页面或接口中。
3. 将控制台从“展示中心”升级为“运行中枢”。
4. 让 X-Agent 具备可持续演进的标准化接口，支撑多智能体、插件市场、权限治理与会话恢复。

---

## 2. 当前现状概述

### 2.1 已有优势

X-Agent 当前已经具备以下基础能力：

- 后端统一入口：`backend/app/main.py`
- 多领域 router 聚合：agents、execution、tools、memory、organization、marketplace、navigation、audit 等
- 前端统一控制台：以 `frontend/src/console` 为核心
- 多中心结构：执行中心、工具中心、记忆中心、组织中心、市场中心、导航中心
- 审计、回放、实时对话、会议室、组织图谱等可视化能力
- API Key、scope、rate limit、审计等平台治理基础

### 2.2 与成熟 agent 内核的差距

相较于成熟的 agentic CLI 内核，X-Agent 目前更偏“平台面”而不是“执行内核”。主要差距在于：

- 工具执行协议不够统一
- 会话恢复与上下文压缩标准还不完整
- 提示工程缺少平台级目录与版本治理
- 插件/市场/能力注册缺少统一 schema
- 任务执行链路、恢复链路、审计链路尚未形成一套闭环
- 前端展示能力强，但运行编排层不够标准化

---

## 3. 升级总原则

### 3.1 平台化原则

所有能力必须沉淀为平台资源，而不是局部页面逻辑。资源应具备：

- 唯一标识
- schema
- 版本
- 状态
- 审计记录
- 恢复能力
- 可追踪来源

### 3.2 协议优先原则

任何新增能力都要先定义协议，再实现 UI 或业务逻辑。协议应覆盖：

- 输入
- 输出
- 错误
- 权限
- 审计
- 回放
- 恢复

### 3.3 提示工程产品化原则

提示词不再视为散落文本，而是平台资产。所有系统提示、角色提示、工具提示、恢复提示、审计提示都要纳入统一管理。

### 3.4 最小破坏原则

升级必须兼容现有 API 和页面结构，优先通过增量增强完成，不破坏现有控制台和路由。

---

## 4. 标准升级目标架构

### 4.1 逻辑分层

建议将 X-Agent 逻辑层划分为六层：

1. **入口层**
   - 登录、初始化、健康检查、入口聚合

2. **编排层**
   - 任务调度、执行控制、审批、恢复

3. **工具层**
   - browser、desktop、workflow、agent、memory、plugins、external tools

4. **记忆层**
   - 会话记忆、长期记忆、摘要、引用、检索

5. **治理层**
   - auth、scope、audit、policy、rate limit、observability

6. **体验层**
   - 控制台、实时聊天、会议室、组织图谱、市场、导航

### 4.2 标准资源模型

建议定义统一资源基类：

- `resource_type`
- `resource_id`
- `title`
- `summary`
- `status`
- `version`
- `owner`
- `scope`
- `risk_level`
- `linked_summaries`
- `audit_trail`
- `recovery_state`

所有中心页面都应使用一致的资源描述方式。

---

## 5. 核心升级项

### 5.1 执行内核升级

目标：把 execution center 从“页面”升级为“执行内核前台”。

标准要求：

- 每个运行动作必须生成 execution trace
- 每个 trace 必须能回放
- 每个执行结果必须可恢复、可审计、可终止
- 支持人工介入点与审批点
- 支持失败重试与状态迁移

建议新增标准能力：

- `dispatch`：生成执行建议
- `plan`：生成执行计划
- `run`：执行任务
- `replay`：回放任务
- `recover`：恢复中断执行
- `approve`：审批敏感操作

### 5.2 工具层标准化

目标：让工具能力从“分散接口”升级为“统一工具协议”。

标准要求：

- 所有工具必须声明 schema
- 工具必须声明权限需求
- 工具必须记录调用输入、输出、耗时、错误
- 工具应支持 enable / disable / install / uninstall / version
- 工具结果应能进入 audit 与 memory

建议统一工具分类：

- `agent`
- `browser`
- `desktop`
- `memory`
- `workflow`
- `plugin`
- `external`

### 5.3 记忆层升级

目标：把 memory center 从数据页升级为“上下文基础设施”。

标准要求：

- 支持短期会话记忆
- 支持长期经验记忆
- 支持引用索引
- 支持摘要压缩
- 支持检索和重放
- 支持“记忆来源 -> 使用场景 -> 可信度”链路

建议统一 memory 资源字段：

- `memory_id`
- `memory_type`
- `origin_session_id`
- `origin_message_id`
- `summary`
- `references`
- `tags`
- `confidence`
- `status`
- `created_at`
- `updated_at`

### 5.4 组织与权限升级

目标：把 organization center 从组织展示升级为权限治理中心。

标准要求：

- 角色、部门、成员、能力授权统一建模
- 所有高风险动作必须可审批
- 权限变更必须审计
- 支持组织级 policy 与 scope
- 支持资源级访问控制

建议新增：

- `capability grants`
- `role bindings`
- `approval workflow`
- `policy enforcement`

### 5.5 市场与扩展升级

目标：把 marketplace center 升级为能力生态入口。

标准要求：

- 能力项具备统一卡片和版本信息
- 插件、工具、技能、资源都应纳入统一发现系统
- 支持安装、启用、禁用、回滚
- 支持兼容性和风险提示
- 支持来源信誉度与审计链

### 5.6 导航与检索升级

目标：让 navigation center 成为统一搜索与快捷操作入口。

标准要求：

- 支持全局检索
- 支持最近页面、收藏页面、快捷入口
- 支持跨中心跳转
- 支持风险等级标识
- 支持按用户上下文动态推荐入口

---

## 6. 提示工程升级标准

提示工程是本次升级的重点之一。建议将提示工程视为平台一级资产。

### 6.1 提示工程目标

- 让系统行为稳定、可解释、可测试
- 让不同角色和不同中心拥有统一的提示定义方式
- 让提示可版本化、可回滚、可审计
- 让提示与工具、记忆、权限、恢复链路协同

### 6.2 提示分类标准

建议将提示工程分为以下类型：

1. **系统提示**
   - 定义平台总行为、边界、风格、优先级

2. **角色提示**
   - 定义 agent、operator、reviewer、planner 等角色职责

3. **工具提示**
   - 定义调用工具时的输入约束、输出格式、失败处理

4. **恢复提示**
   - 定义任务中断、重试、回放、继续执行的策略

5. **审计提示**
   - 定义如何输出可追踪、可解释的审计记录

6. **记忆提示**
   - 定义哪些内容可写入长期记忆，如何抽取摘要与引用

7. **市场提示**
   - 定义插件/工具/能力的推荐、安装、启用标准

### 6.3 提示目录结构建议

建议在根目录建立统一提示工程目录，例如：

- `prompts/system/`
- `prompts/roles/`
- `prompts/tools/`
- `prompts/recovery/`
- `prompts/audit/`
- `prompts/memory/`
- `prompts/marketplace/`
- `prompts/navigation/`

每个提示文件建议包含：

- `id`
- `name`
- `version`
- `purpose`
- `scope`
- `inputs`
- `outputs`
- `constraints`
- `examples`
- `owner`
- `last_updated`

### 6.4 提示版本治理

必须支持：

- 版本号
- 变更说明
- 回滚策略
- A/B 测试
- 按角色或环境启用

建议引入：

- `prompt registry`
- `prompt loader`
- `prompt validator`
- `prompt diff`
- `prompt telemetry`

### 6.5 提示工程与执行链路的关系

提示工程不能只服务聊天，还应直接影响：

- 任务分解
- 工具选择
- 审批判断
- 恢复策略
- 记忆抽取
- 风险识别

换句话说，提示工程应该进入执行内核，而不是停留在 UI 层。

---

## 7. 标准数据契约

### 7.1 通用返回结构

建议所有控制中心 API 统一返回：

- `resource_type`
- `resource_id`
- `primary`
- `linked_summaries`
- `status`
- `risk_level`
- `version`
- `updated_at`

### 7.2 统一动作结构

建议统一 action：

- `open_*`
- `select_*`
- `create_*`
- `update_*`
- `approve_*`
- `recover_*`
- `replay_*`
- `install_*`
- `enable_*`
- `disable_*`
- `search_*`

### 7.3 统一审计结构

审计记录建议包含：

- who
- when
- what
- where
- why
- input
- output
- duration
- result
- risk

---

## 8. 推荐落地顺序

### 第一阶段：标准化骨架

1. 定义统一 resource schema
2. 定义统一 action schema
3. 定义统一 audit schema
4. 定义统一 prompt schema
5. 定义统一 memory schema

### 第二阶段：执行内核

1. 完善 dispatch / plan / run / recover
2. 建立 execution trace
3. 建立中断恢复机制
4. 建立审批点

### 第三阶段：提示工程平台化

1. 建立 prompts 目录
2. 建立 prompt registry
3. 建立版本与回滚机制
4. 将提示接入执行链路

### 第四阶段：扩展与生态

1. 工具市场协议统一
2. 插件安装与启用标准化
3. 能力兼容性检测
4. 风险评级和审计联动

### 第五阶段：治理与观测

1. 全链路 trace
2. 指标面板
3. 审计回放
4. 策略与权限联动

---

## 9. 建议的新目录结构

以下为推荐结构，不要求一次性全部落地：

```text
backend/
  app/
    core/
    api/
    services/
    prompts/
    schemas/
    orchestration/
    recovery/
    audit/
    memory/
frontend/
  src/
    console/
      pages/
      state/
      components/
      prompts/
      workflows/
      audit/
      recovery/
      memory/
prompts/
  system/
  roles/
  tools/
  recovery/
  audit/
  memory/
  marketplace/
  navigation/
docs/
  architecture/
  standards/
  prompt-engineering/
```

---

## 10. 成功验收标准

升级完成后，X-Agent 应满足以下标准：

- 任意任务都有可追踪执行链
- 任意工具调用都能审计和回放
- 任意中断任务都能恢复
- 任意提示都可版本化管理
- 任意能力都可统一发现和启用
- 任意中心页面都遵循统一资源契约
- 控制台不仅能看，还能直接治理运行态

---

## 11. 结论

X-Agent 当前已经具备一个“平台控制台”的雏形，下一步最重要的升级方向不是增加页面数量，而是补齐“agent 内核”的标准化能力。

如果说 Claude Code 的优势是“深度执行”，那么 X-Agent 的目标应当是：

> 在具备深度执行能力的同时，成为更适合团队治理、组织协同和平台化扩展的 Agent OS。

而提示工程，应当作为这个 OS 的第一等公民纳入体系。
