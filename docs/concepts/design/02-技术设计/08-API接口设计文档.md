# X-Agent API 接口设计文档

## 文档概述

**版本：** v5.0  
**更新时间：** 2026-05-12  
**适用范围：** 当前代码中真实存在的 API 路由、权限边界、观测接口、记忆接口、工作流接口和基础运维接口

本文档以当前代码为准，同时把你已经确认的核心需求写进来，保留主体方向，不再混入未实现的企业级平台幻觉。

---

## API 层在整体架构中的定位

API 层是 X-Agent 的统一入口，承担：

- 请求接入
- 身份认证与作用域检查
- 领域路由分发
- 观测和审计入口
- 与 Agent / Memory / Workflow / Automation / Ops 等核心模块的连接

---

## 当前代码中真实存在的 API 组成

### 应用入口
- `backend/app/main.py`

### 路由层
- `backend/app/api/*.py`

### 依赖与权限
- `backend/app/dependencies.py`
- `backend/app/core/security.py`
- `backend/app/core/contracts.py`
- `backend/app/api/errors.py`

---

## 当前已实现的 API 领域

### 1. 基础接口
- `GET /`
- `GET /health`
- `GET /ready`

### 2. 认证、用户、租户、安全
- `auth`
- `users`
- `tenants`
- `security`
- `migration`

### 3. Agent、Run、Trace、Tools、Approvals
- `agents`
- `runs`
- `traces`
- `tools`
- `approvals`

### 4. Memory
- `memory`

### 5. Workflows
- `workflows`
- `workbench`

### 6. 可观测性与运维
- `overview`
- `ops`
- `metrics`
- `audit`
- `org`

### 7. 协作、浏览器、桌面
- `collaboration`
- `browser`
- `desktop`
- 人机协同 / 人工接管
- 浏览器会话 / 运行记录
- 桌面模式 / WebView

### 8. 创造力 / 开源检索
- 开源资源发现接口（规划）
- 方案评估接口（规划）
- 结果沉淀接口（规划）
- 候选短名单
- 对比报告
- 风险报告
- 接入计划
- 决策日志

---

## 当前 API 风格

当前仓库的 API 风格是典型的 FastAPI 领域分层风格：

- REST 为主
- FastAPI + Pydantic 建模
- 统一异常处理
- 请求 ID / trace / audit 贯穿
- scope / principal 权限检查在依赖层执行

---

## 你确认过的接口需求与现状对齐

### 1. Agent 入口
API 层要支撑：

- 先编排，再执行
- 任务拆解到可执行步骤
- 子代理级委派
- 工具调用与审批
- 记忆联动
- 自我进化记录
- 创造力 / 开源检索的外部资源接入

### 2. Memory 入口
API 层要支撑：

- 分层记忆
- 会话连续性
- 记忆修订 / 回滚
- 共享 / 作用域控制
- 多源检索
- 巩固 / 污染检查

### 3. Workflow 入口
API 层要支撑：

- 工作流定义 / 执行 / 调度
- 对话式创建
- 审批门 / 恢复 / 补偿
- 时间线 / 关联 / 记忆同步

### 4. Automation 入口
API 层要支撑：

- 浏览器自动化
- 桌面 / WebView
- RPA 任务编排
- 人机协同
- 审计与回放

### 5. Security 入口
API 层要支撑：

- auth / api key / rbac / scope / tenant / user
- 高风险审批
- 破坏性操作防护
- 审计与回滚

### 6. Observability 入口
API 层要支撑：

- trace / run / audit / correlation
- overview / metrics / ops
- readiness / health
- Langfuse 接入
- 回放 / Debug
- 事件导出
- Request ID 贯穿全链路
- 延迟 / 性能统计

---

## 当前记忆接口现状

`backend/app/api/memory.py` 是当前最明确、最完整的领域路由之一，已经覆盖：

- 记忆写入
- 记忆查询
- 记忆 session
- 记忆 revision
- rollback
- pollution 检查
- export / import
- correlation
- consolidate
- count

### 记忆 API 的主体特点

- 强依赖 `Principal` 和 scope
- 与 audit / Langfuse 结合
- 支持 session 级别的记忆组织
- 部分能力会根据 memory backend 是否实现而启用

---

## 典型响应形态

### 健康检查

```json
{
  "status": "ok",
  "service": "X-Agent"
}
```

### 就绪检查

```json
{
  "status": "ready",
  "service": "X-Agent",
  "components": {
    "memory": "ok",
    "qdrant": "ok",
    "trace": "ok",
    "runs": "ok",
    "workflows": "ok",
    "audit": "ok",
    "browser": "ok",
    "observability": "ok"
  }
}
```

### Memory 返回对象

当前 memory 路由会返回：

- `MemoryItem`
- `SessionRecord`
- `MemorySearchHit`
- `MemoryConsolidationResult`
- `MemoryExportBundle`
- `MemoryRollbackResult`

---

## 当前 API 设计原则

1. **以当前路由为准**
   - 只写代码中已存在的领域接口

2. **以权限和作用域为边界**
   - 敏感接口依赖 principal / scope

3. **以观测闭环为特征**
   - audit + Langfuse + trace + run 形成记录链路

4. **不写成虚构大而全平台**
   - 技能市场、完整 gRPC、复杂限流体系、完整知识库等不作为现状

5. **保留你的原创主体**
   - Agent、Memory、Workflow、Automation、Security、Collaboration、Evolution 全部继续保留在文档主线上

---

## 建议后续保留的 API 文档重点

后面如果继续补充，建议集中在：

- 路由总表
- 权限与 scope 说明
- memory session 规范
- trace / run / correlation 说明
- readiness 与健康检查说明

---

## 结论

当前 API 层已经形成了比较完整的原创内核接口骨架，尤其是 memory / run / trace / audit / browser 这条链路已经可以支撑后续文档继续精细化，但必须严格按当前代码边界来写。