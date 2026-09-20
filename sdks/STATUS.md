# 状态：冻结的外围原型（Frozen peripheral — NOT covered by CI or release gates）

**评估日期：** 2026-09-20（T11 外围冻结，见 `docs/decisions/CONVERGENCE_DECISIONS.md`）

## 这是什么
5 个手写的 Partner API 客户端（Go / Java / JavaScript-TS / Python），共 6 个文件。

## 当前定位
- 无测试、无打包发布（不在 PyPI/npm/Go modules 上）、不参与 CI。
- Partner API 本身在后端 API 面中的挂载状态以 `docs/API_INVENTORY.md` 为准；
  SDK 方法与真实路由的一致性**未经校验**。
- 不包含在 v0.2.0-beta 发布范围内。

## 恢复条件（何时解冻）
1. 确定 Partner API 契约并冻结；
2. 用 OpenAPI 生成替代手写（推荐 openapi-generator），或为手写 SDK 建立契约测试；
3. 有明确维护者认领。

在此之前按"只读归档"对待。
