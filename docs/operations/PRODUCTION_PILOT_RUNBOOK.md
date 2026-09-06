# X-Agent 生产试点 Runbook（1-2 周试点期）

> 目标：在受控真实环境验证 v0.4.0-rc2+ 的长时运行稳定性，产出试点报告作为
> GA（0.4.0 正式版）放行依据。rc1 口径沿用的"无长时运行证据"边界在此关闭。

## 0. 前置条件清单

| 项 | 要求 | 检查命令 |
|---|---|---|
| 主机 | 2C4G 起步（Docker 沙箱建议 4C8G） | `docker --version` |
| 外部存储 | PostgreSQL 14+ / Redis 7 / Qdrant 1.11+（或同 compose 栈） | `docker compose -f docker-compose.postgres.yml up -d` |
| LLM | 任一 provider key（OpenAI/DeepSeek/Anthropic）或本地 Ollama | `echo $XAGENT_OPENAI_API_KEY` |
| 密钥 | 32+ 字符随机 JWT/加密密钥 | `python scripts/generate_secrets.py` |

## 1. 部署（生产守卫会 fail-fast 拦截缺失配置）

```bash
# 生产必配（生产守卫清单）
export XAGENT_APP_MODE=production
export XAGENT_DATABASE_URL=postgresql://xagent:<pw>@<host>:5432/xagent
export XAGENT_MEMORY_BACKEND=postgres
export XAGENT_ADMIN_STORE_BACKEND=postgres
export XAGENT_WORKFLOW_STORE_BACKEND=db
export XAGENT_JWT_SECRET=<64字符> XAGENT_ENCRYPTION_KEY=<32字符>
export XAGENT_REQUIRE_API_KEY=true
# 数据库连接池按负载调（默认 5+10，见已知边界）
export XAGENT_DATABASE_POOL_SIZE=20

docker compose -f docker-compose.postgres.yml up -d   # 外部栈
docker build -t x-agent:rc2 . && docker run -p 8000:8000 --env-file .env.production x-agent:rc2
```

## 2. 试点验收用例（每日执行）

| # | 场景 | 通过标准 |
|---|---|---|
| V1 | 启动健康 | `/health` 200、`/ready` 200、471+ 路由挂载 |
| V2 | 基础对话 | Web/CLI 各 10 轮任务，流式事件完整（plan→tool_call→completion） |
| V3 | 技能学习闭环 | 连跑同类任务 5+，`custom-skills/` 出现沉淀技能且可被调用 |
| V4 | 记忆检索 | 写入 1000+ 条后搜索 <100ms（FTS 生效：日志 `fts=True`） |
| V5 | 定时任务 | `/api/scheduler/tasks` 建 cron 任务，到点 agent.run 真实执行 |
| V6 | 断点续跑 | 人为中断长任务，`POST /api/v1/checkpoints/{id}/resume` 恢复 |
| V7 | 沙盒任务 | 提交 shell 任务，重启后 `/api/v1/sandbox/tasks/{id}` 仍可查 |
| V8 | MCP | filesystem 插件（配置 allowed_paths）握手+读写往返 |
| V9 | 审批流 | HIGH 风险工具触发审批，approve 后继续执行 |
| V10 | 优雅关闭 | SIGTERM 后 drain、无任务丢失、重启恢复 |

## 3. 监控与观察点

- 指标：`/metrics`（Prometheus 格式）——QPS、LLM 延迟/失败率、任务队列深度
- 日志：`logs/` + 审计链 `data/audit.jsonl`（哈希链完整性 `GET /api/v1/audit/verify`）
- 已知观察项：
  - DB 连接池饱和（QueuePool timeout 日志）→ 调 POOL_SIZE
  - checkpoint/task JSONL 增长 → 容量上限自动压缩已内置，观察压缩触发
  - LLM 配额消耗（quota 模块）

## 4. 回滚

- 镜像回退上一 tag（v0.4.0-rc1）；数据层向后兼容（Postgres schema 由
  alembic 管理，`alemlc downgrade` 仅在 schema 变更时需要）

## 5. 试点报告模板

产出：`commercial_audit/pilot_report_YYYY-MM-DD.md`——V1-V10 结果、
事故/异常清单、资源消耗曲线、GA 放行建议（放行/有条件放行/延期）。
