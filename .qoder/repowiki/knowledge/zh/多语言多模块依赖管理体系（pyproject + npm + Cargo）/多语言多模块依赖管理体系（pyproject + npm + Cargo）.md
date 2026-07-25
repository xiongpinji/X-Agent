---
kind: dependency_management
name: 多语言多模块依赖管理体系（pyproject + npm + Cargo）
category: dependency_management
scope:
    - '**'
source_files:
    - pyproject.toml
    - requirements.txt
    - requirements-lock.txt
    - frontend/package.json
    - frontend/package-lock.json
    - extension/package.json
    - extension/package-lock.json
    - desktop/Cargo.toml
    - cloud/requirements.txt
---

## 1. 体系概览

X-Agent 是一个跨语言、多子模块的 monorepo，依赖管理按语言/工具链拆分到各自目录，通过顶层 Makefile、Docker Compose 与 pre-commit 统一编排安装与构建。核心策略是：

- Python 后端：以 `pyproject.toml` 为单一事实源，使用 `uv pip compile` 生成 `requirements-lock.txt` 锁定全部传递依赖；同时保留一份 `requirements.txt` 作为人类可读的生产清单。
- Node.js 前端与扩展：各子模块独立 `package.json` + `package-lock.json`，分别由 Vite/React 与 Chrome Extension 生态管理。
- Rust 桌面端：`desktop/Cargo.toml` 声明 Tauri 应用依赖，未启用 Cargo.lock 提交（仅源码）。
- 云端服务：`cloud/requirements.txt` 单独列出云同步/加密服务的依赖，版本与主后端存在差异，需独立维护。

## 2. 关键文件与位置

| 语言/模块 | 声明文件 | 锁定文件 | 说明 |
|---|---|---|---|
| Python 后端 | `pyproject.toml` | `requirements-lock.txt` | 主包 `x-agent-core`，定义 core/cli/prod/dev/test/monitoring extras |
| Python 生产清单 | `requirements.txt` | — | 人类可读的生产依赖，注释中记录安全与兼容性决策 |
| Node Web 前端 | `frontend/package.json` | `frontend/package-lock.json` | React + Vite 控制台 UI |
| Node Chrome 扩展 | `extension/package.json` | `extension/package-lock.json` | Manifest V3 浏览器自动化扩展 |
| Rust 桌面端 | `desktop/Cargo.toml` | （未提交） | Tauri 1.5 桌面客户端 |
| 云端服务 | `cloud/requirements.txt` | — | 独立的云同步/加密服务，版本与主后端不同步 |
| 商用审计脚本 | `commercial_audit/package.json` | `commercial_audit/package-lock.json` | 一次性审计工具，不纳入主构建 |

## 3. 架构与约定

### 3.1 Python 依赖分层

- **单一事实源**：`pyproject.toml` 中的 `[project.dependencies]` 与 `[project.optional-dependencies]` 是权威来源，所有环境通过 extras 组合：
  - `cli`：Typer/Rich/Prompt-toolkit/YAML
  - `prod`：psycopg-binary/celery/redis/prometheus-client
  - `dev`：pytest/ruff/black/isort/flake8/bandit/pip-audit/mypy/pylint/pre-commit
  - `test`：pytest-cov/locust
  - `monitoring`：prometheus-client
- **锁定机制**：通过命令 `uv pip compile pyproject.toml --python-version 3.11 --extra cli --extra prod --overrides .xagent_runtime/reports/requirements-lock-overrides.txt --output-file requirements-lock.txt` 生成全量锁定文件，支持 `.xagent_runtime/reports/requirements-lock-overrides.txt` 覆盖特定包的版本（如 fastapi/starlette/pydantic 等）。
- **兼容性与安全注释**：`requirements.txt` 每行附带注释，解释为何放宽或固定版本（如 cp313 wheel 可用性、sandbox 验证结果），并标注“SECURITY: All versions are pinned to known-secure releases”。

### 3.2 Node.js 子模块隔离

- 每个前端子项目拥有独立的 `package.json`，依赖范围使用 `^` 语义化版本，锁定在各自的 `package-lock.json` 中。
- 前端工程化：Vite + TypeScript + Tailwind + ESLint + Prettier，构建脚本在 package.json 中集中管理。
- Chrome 扩展无运行时依赖，仅 devDependencies（eslint/jest/prettier），通过 zip 打包发布。

### 3.3 Rust 桌面端

- `desktop/Cargo.toml` 直接声明 Tauri 1.5 及 tokio/reqwest/sqlx 等依赖，features 控制自定义协议能力。
- 未提交 `Cargo.lock`，意味着每次编译可能拉取最新兼容版本，适合开发但生产构建需额外锁定步骤。

### 3.4 云端服务独立依赖

- `cloud/requirements.txt` 与主后端版本存在显著差异（如 fastapi 0.104 vs 0.115+、qdrant-client 2.7 vs 1.11），表明云同步服务是独立部署单元，需单独维护其依赖生命周期。

## 4. 开发者应遵循的规则

1. **Python 新增依赖必须修改 `pyproject.toml`**，并通过 `uv pip compile` 重新生成 `requirements-lock.txt`，禁止直接编辑锁定文件。
2. **生产环境安装使用 `requirements-lock.txt`**，确保可重现构建；本地开发可使用 `pip install -e ".[dev,cli]"` 安装 extras。
3. **Node.js 子模块各自更新**：在对应目录执行 `npm i` / `npm update`，提交 `package-lock.json`，不要跨目录共享 node_modules。
4. **Rust 桌面端如需固定版本**，应在 CI 中运行 `cargo build` 生成 `Cargo.lock` 并提交，避免构建漂移。
5. **云端服务依赖变更需独立 PR**，不得与主后端混改，注意版本差异带来的 API 不兼容风险。
6. **安全扫描**：CI 中已集成 `pip-audit` 与 `bandit`，新增依赖后需确保无已知漏洞告警。
7. **版本一致性**：顶层 `pyproject.toml` 中的 `version = "0.2.0-alpha"` 是所有组件版本的单一事实源，前端/扩展的 `package.json` 也保持相同版本号，变更时需同步更新。