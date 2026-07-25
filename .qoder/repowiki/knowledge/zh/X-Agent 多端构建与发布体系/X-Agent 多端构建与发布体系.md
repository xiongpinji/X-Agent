---
kind: build_system
name: X-Agent 多端构建与发布体系
category: build_system
scope:
    - '**'
source_files:
    - Makefile
    - pyproject.toml
    - Dockerfile
    - docker-compose.yml
    - deploy.sh
    - .github/CI-CD-SUMMARY.md
    - frontend/package.json
    - desktop/Cargo.toml
    - extension/package.json
---

## 1. 系统概览

X-Agent 采用**以 Python 生态为核心、Docker/K8s 为交付载体、Makefile 统一编排**的多端构建体系。仓库同时包含后端 FastAPI、Web 前端（Vite+React）、CLI（Typer）、桌面客户端（Tauri/Rust）、Chrome 扩展（Manifest V3）以及 SDK，各子模块通过顶层 Makefile 和 Docker Compose 串联起来，形成统一的开发/测试/打包/部署流水线。

- **Python 包管理**: `pyproject.toml` 作为单一版本与依赖事实源，使用 setuptools + wheel 构建；可选依赖通过 `[project.optional-dependencies]` 按 cli/prod/dev/test/monitoring 切分。
- **构建入口**: 根目录 `Makefile` 提供 install / build / test / lint / type-check / security / docker-build / deploy 等目标，是开发者与 CI 的统一入口。
- **容器化**: 根级 `Dockerfile` 使用多阶段构建（builder/runtime），`docker-compose.yml` 编排 Postgres、Redis、Qdrant、Neo4j、xagent-api/xagent-worker/xagent-beat 等服务。
- **Kubernetes 部署**: `deploy.sh` 封装镜像构建、推送、`kubectl set image` 滚动更新与健康检查；`deployment/helm` 与 `deployment/k8s` 提供 Helm Chart 与直写清单。
- **CI/CD**: `.github/CI-CD-SUMMARY.md` 描述了 test/lint/security/deploy/branch-protection 五个 GitHub Actions workflow 的触发条件、产物与 Secrets 要求（实际 yml 文件由文档驱动生成）。

## 2. 关键文件与位置

| 类别 | 关键文件 |
|------|----------|
| Python 包定义 | `pyproject.toml`, `requirements.txt`, `requirements-lock.txt` |
| 构建编排 | `Makefile` |
| 容器镜像 | `Dockerfile` |
| 本地/集成环境 | `docker-compose.yml`, `docker-compose.test.yml`, `docker-compose.postgres.yml`, `docker-compose.performance.yml` |
| 生产部署脚本 | `deploy.sh` |
| K8s/Helm 清单 | `deployment/helm/`, `deployment/k8s/` |
| 监控栈编排 | `monitoring/docker-compose.monitoring.yml` |
| 前端构建 | `frontend/package.json`, `frontend/vite.config.ts`, `frontend/Dockerfile` |
| 桌面客户端构建 | `desktop/Cargo.toml`, `desktop/tauri.conf.json`, `desktop/build.rs` |
| Chrome 扩展构建 | `extension/package.json`, `extension/manifest.json` |
| CI/CD 文档 | `.github/CI-CD-GUIDE.md`, `.github/CI-CD-SUMMARY.md`, `.github/GITHUB-ACTIONS-BEST-PRACTICES.md` |
| 代码质量配置 | `.pre-commit-config.yaml`, `.ruff-blocking-baseline.txt`, `mypy.ini`, `pytest.ini`, `pytest_comprehensive.ini` |

## 3. 架构与约定

### 3.1 版本与依赖策略
- **单一版本源**: `pyproject.toml` 中 `version = "0.2.0-alpha"` 是全仓所有版本宣称的事实源，Makefile 通过 `git describe --tags --always` 派生 `VERSION` 并注入 Docker 镜像标签。
- **锁定依赖**: 构建镜像时使用 `requirements-lock.txt` 保证可重现；本地开发通过 `pip-compile pyproject.toml -o requirements.txt` 同步。
- **可选依赖切分**: `dev`/`test`/`prod`/`cli`/`monitoring` 四类 extras，安装时按需选择，避免生产镜像携带开发工具。

### 3.2 构建流水线
```
make ci-full
  → clean
  → ruff/pylint/mypy/bandit/pip-audit/safety
  → pytest (unit/integration/contract/performance)
  → docker-build (多阶段, 注入 VERSION/BUILD_DATE/VCS_REF)
```
- `make build` 仅执行 format→lint→type-check→test，用于本地快速验证。
- `make docker-push` 将镜像推送到 `ghcr.io/x-agent-core:<VERSION>`。

### 3.3 容器与服务编排
- **Dockerfile**: builder 阶段安装编译依赖并 `pip install -e .`，runtime 阶段仅保留运行库并以非 root 用户启动。
- **docker-compose.yml**: 一键拉起 Postgres/Redis/Qdrant/Neo4j + xagent-api + xagent-worker + xagent-beat，并通过 healthcheck 保障启动顺序。
- **monitoring**: `monitoring/docker-compose.monitoring.yml` 独立编排 Prometheus/Grafana/Alertmanager/Elasticsearch/Kibana/Jaeger。

### 3.4 多端构建差异
- **后端**: 纯 Python，遵循上述 Makefile/Dockerfile 流程。
- **前端**: `frontend/` 使用 Vite + React，`package.json` 定义 build/dev/test 命令，另有独立 `frontend/Dockerfile` 用于 Nginx 静态资源服务。
- **桌面客户端**: `desktop/` 基于 Tauri + Rust，`Cargo.toml` 声明 Rust 依赖，`tauri.conf.json` 配置打包参数，`build.rs` 参与构建钩子。
- **Chrome 扩展**: `extension/` 使用 Manifest V3，`package.json` 负责打包脚本，`manifest.json` 声明权限与入口。

### 3.5 部署模型
- **本地**: `docker compose up` 或 `make run`（uvicorn 热重载）。
- **Staging/Production**: `./deploy.sh <env> <version>` 完成镜像构建→推送→`kubectl set image` 滚动更新→健康检查→冒烟测试→报告生成，失败自动回滚。
- **K8s**: `deployment/helm/` 提供 Helm Chart，`deployment/k8s/` 提供直写 Deployment/Service/ConfigMap 清单，配合 `deploy.sh` 使用。

## 4. 开发者应遵循的规则

1. **版本变更**: 只改 `pyproject.toml` 中的 `version`，不要单独维护 CHANGELOG/README 中的版本号。
2. **依赖管理**: 新增依赖先写入 `pyproject.toml` 对应 extra，再 `make requirements-update` 生成 `requirements.txt`，提交两者。
3. **代码质量**: 提交前运行 `make pre-commit-run`，确保 ruff/isort/black/mypy/bandit 全部通过；PR 必须通过 CI 的 test/lint/security 任务。
4. **测试标记**: 新测试需加上 `-m unit|integration|contracts|e2e|performance` 标记，以便 `make test-*` 精准执行。
5. **容器镜像**: 修改 `Dockerfile` 后务必 `make docker-build` 验证多阶段构建成功；生产镜像禁止携带 dev 依赖。
6. **环境变量**: 新增运行时配置需在 `docker-compose.yml` 的 `xagent-api` 服务中添加默认值，并在 `.env.example` 中补充说明。
7. **多端改动**: 涉及前端/桌面/扩展的 PR 需额外在对应子目录执行其原生构建命令（如 `cd frontend && npm run build`），确保该子模块仍可独立构建。
8. **部署操作**: 生产发布只能通过 `make deploy-production` 或 `./deploy.sh production <tag>` 执行，禁止直接 `kubectl apply` 绕过健康检查与回滚逻辑。
