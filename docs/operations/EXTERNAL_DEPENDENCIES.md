# 外部依赖项清单（工程侧无法自行推进，需 Owner 决策/采购）

> 2026-09-06 整理。每项附"工程侧已就绪的部分"与"待 Owner 动作"。

## 1. 真实 Telegram Bot 端到端

- **已就绪**：网关 API（register/status/send/broadcast/start/stop）+ agent 双向回路
  + webhook 融合（代码侧 61 测试绿）；冒烟脚本 `scripts/telegram_smoke.py`
- **待 Owner**：@BotFather 申请 bot → `XAGENT_TELEGRAM_BOT_TOKEN=... python scripts/telegram_smoke.py`
  → 真机发消息验证"消息→agent→回复"。若走 webhook 需公网可达 URL（内网用轮询模式即可）

## 2. 生产试点环境

- **已就绪**：`docs/operations/PRODUCTION_PILOT_RUNBOOK.md`（部署清单 + V1-V10
  验收用例 + 监控点 + 回滚），Docker 构建链（lock 平台标记修复后 CI 可产镜像）
- **待 Owner**：提供试点主机/云环境（2C4G+，Postgres/Redis/Qdrant 或 compose 栈），
  按 runbook 跑 1-2 周，产出试点报告

## 3. 桌面端代码签名证书

- **已就绪**：msi/nsis 双安装包本地可产（`desktop/target/release/bundle/`）；
  `tauri.conf.json` 已预留 `certificateThumbprint` 字段与 timestampUrl
- **待 Owner**：采购 OV/EV 代码签名证书（EV 可过 SmartScreen 信誉冷启动），
  证书入证书库后填 thumbprint，`npx tauri build` 自动签名

## 4. 移动端商店发布

- **已就绪**：Expo 壳 + API 配置化 + 契约对齐（31 测试绿）+ Settings 连接测试屏
- **待 Owner**：Apple Developer（$99/年）/ Google Play（$25）账号、隐私政策
  URL、商店素材；`cd mobile && npx expo export` 后经 EAS Build 或 Xcode/AS 打包

## 5. SOC 2 认证（企业采购准入）

- **已就绪**（审计证据基础）：审计哈希链+轮转、RBAC+租户隔离、SSO/SCIM、
  GDPR 端点、SBOM（sbom.json）、pip/npm audit 清零、KMS 信封加密
- **待 Owner**：选择审计方（Type I 3-6 月 / Type II 6-12 月观察期）、启动
  合规流程；工程侧配合出具证据

## 6. 第三方渗透测试

- **已就绪**：安全设计文档（backend/app/core/sandbox/SECURITY_DESIGN.md）、
  安全自测套件（tests -m security）、依赖漏洞清零基线
- **待 Owner**：采购渗透测试服务（建议 GA 前 4-6 周启动），范围：Web API /
  沙箱逃逸 / 多租户隔离

## 7. IDE 扩展（五端最后空白，工程可推进但需产品决策）

- **已就绪地基**：@xagent/sdk（sdks/typescript）提供 VS Code 扩展所需的
  流式客户端/审批/断线续订，README 附接入指引
- **待决策**：是否立项（建议 VS Code先行，复用 SDK；工作量约 1-2 周可出
  MVP：侧栏对话 + @文件 + 审批通知）
