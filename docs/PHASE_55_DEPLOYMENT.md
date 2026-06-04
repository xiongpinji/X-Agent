# Phase 5.5 云沙箱执行引擎 — 部署与使用指南

X-Agent 的云沙箱引擎对标 OpenAI Codex 的隔离执行模型,但**开源自托管**:代码不出内网、任意 LLM、多租户隔离。本文说明如何部署并使用。

## 一、架构

```
POST /api/v1/sandbox/tasks  ──┐
POST /api/v1/sandbox/webhook/github ──┤
                              ▼
                         TaskQueue (优先级堆)
                              ▼
                    SandboxOrchestrator (持久 drain loop)
                              ▼
              ┌───────────────┼───────────────┐
        SandboxWorker    SandboxWorker    SandboxWorker   (并行)
              ▼               ▼               ▼
        DockerSandbox    DockerSandbox    DockerSandbox
        (容器隔离 / 无 Docker 时降级子进程)
```

## 二、两种执行后端

`DockerSandbox` 在启动时探测 Docker 守护进程(`is_docker_available()`,结果缓存):

| 后端 | 触发条件 | 隔离强度 |
|------|---------|---------|
| **docker** | Docker 守护进程可达 + `docker` 包已装 | 完整容器隔离(网络/内存/CPU 限制 + 只读根) |
| **subprocess** | 无 Docker(无守护进程/无 root/CI) | 无隔离,仅进程级,网络通过代理尽力阻断 |

**关键:** 不装 `docker` 包或没有守护进程时,引擎仍能工作(自动降级),但**没有真正的隔离**。生产环境务必启用 Docker 后端。

## 三、启用 Docker 后端

### 3.1 安装依赖

```bash
pip install "docker>=7.0.0"   # 已在 requirements.txt(可选段)
```

### 3.2 让容器内能访问 Docker

X-Agent 自身跑在容器里时,sandbox 任务需要再起容器(Docker-out-of-Docker)。挂载宿主 Docker socket:

```yaml
# docker-compose.yml 的 api 服务
services:
  api:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock   # DooD:复用宿主 Docker
    # 安全提示:挂 socket = 给容器宿主级权限,仅在受信任环境用
```

> 更强隔离选 gVisor(`runsc`)或独立 DinD 服务。生产高安全场景建议 DinD + 网络隔离。

### 3.3 Dockerfile 已就绪

runtime 阶段已装 `git`(IssueToPR pipeline 的 clone/commit/push 需要)。

## 四、API 使用

### 4.1 提交任务(fire-and-forget)

```bash
curl -X POST http://localhost:8000/api/v1/sandbox/tasks \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"build","command":"pip install -e . && pytest -q","image":"python:3.11-slim","timeout_seconds":300,"enable_network":true}'
# → {"task_id":"task_abc123","status":"queued"}
```

### 4.2 轮询结果

```bash
curl http://localhost:8000/api/v1/sandbox/tasks/task_abc123 -H "x-api-key: $API_KEY"
# → {"task_id":"task_abc123","status":"completed","backend":"docker","steps":[...]}
```

### 4.3 列出任务

```bash
curl http://localhost:8000/api/v1/sandbox/tasks -H "x-api-key: $API_KEY"
```

## 五、GitHub Issue → PR 自动化

### 5.1 配置 webhook 密钥

```bash
export XAGENT_GITHUB_WEBHOOK_SECRET="your-strong-secret"   # 不设则 webhook 全部 403
export XAGENT_GITHUB_TOKEN="ghp_..."                       # PR 创建用
```

### 5.2 在 GitHub 仓库配 webhook

- Payload URL: `https://your-host/api/v1/sandbox/webhook/github`
- Content type: `application/json`
- Secret: 与 `XAGENT_GITHUB_WEBHOOK_SECRET` 一致
- Events: Issues

### 5.3 流程

Issue 被 assign → webhook(HMAC-SHA256 校验)→ 入队 → clone → 建分支 → fix_runner 改代码 → 跑测试 → commit → push → 开 PR → 回评论。

> **安全:** webhook 只入队任务,**绝不直接执行 Issue 正文里的指令**。Agent 在正常 policy/approval 门控下决定怎么做。

## 六、权限

所有 `/api/v1/sandbox/*`(除 webhook)需 `sandbox:run` scope。已加到 `admin`/`developer` 角色。webhook 用 HMAC 签名校验,无密钥配置则拒绝(不允许未签名执行)。

## 七、安全模型

| 层 | 措施 |
|----|------|
| 容器隔离 | 网络默认禁用、内存/CPU 上限、独立 workspace 挂载 |
| webhook | HMAC-SHA256 constant-time 校验,无密钥即拒 |
| 注入防护 | webhook 只入队,不执行 Issue 正文指令 |
| token | git URL 内嵌 token 在日志中脱敏 |
| 鉴权 | sandbox:run scope 强制 |

## 八、降级与排障

| 现象 | 原因 | 处理 |
|------|------|------|
| `backend: subprocess`(期望 docker) | 守护进程不可达 / docker 包未装 / 无 socket 挂载 | 装 docker 包 + 挂 socket |
| git clone 失败 | runtime 容器无 git | 已修(Dockerfile 装了 git);自建镜像确认 |
| webhook 全 403 | `XAGENT_GITHUB_WEBHOOK_SECRET` 未设 | 设密钥 |
| task 卡 queued | worker 未启动 | 确认 app 经 startup 事件启动(非 `--reload` 裸跑) |

## 九、测试

```bash
pytest tests/test_docker_sandbox.py tests/test_sandbox_orchestrator.py tests/test_sandbox_api.py -q
# issue_to_pr 较慢,单独跑:
pytest tests/test_issue_to_pr_pipeline.py -q
```

38 个测试覆盖:容器降级、并行编排、API 提交/轮询/webhook 签名、Issue→PR 全链路。
