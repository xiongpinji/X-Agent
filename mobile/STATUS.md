# 状态：冻结的外围原型（Frozen peripheral — NOT covered by CI or release gates）

**评估日期：** 2026-09-20（T11 外围冻结，见 `docs/decisions/CONVERGENCE_DECISIONS.md`）

## 这是什么
React Native（Expo：`package.json`、`eas.json`、`src/*.tsx`）移动端原型，
含 Android/iOS 生物识别原生模块（`BiometricAuthModule.kt` / `.swift`）。

## 当前定位
- **不参与** CI 门禁；未验证 `npm install` / EAS 构建能通过。
- **不包含**在 v0.2.0-beta 发布范围内。
- 目录内大量"交付报告/实现指南"（`*_DELIVERY_REPORT.md` 等）是历史文档，
  其声明的完成度未经本轮治理复核。
- 所依赖的后端接口以 `docs/API_INVENTORY.md`（323 paths / 361 ops）为准。

## 恢复条件（何时解冻）
1. 后端 API 契约稳定一个版本周期；
2. 建立 mobile CI（typecheck + EAS preview build）并连续绿色；
3. 有明确维护者认领。

在此之前按"只读归档"对待。
