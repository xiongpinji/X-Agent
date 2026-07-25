# X-Agent Core

X-Agent Core is an open-source autonomous agent framework designed for building intelligent, self-evolving systems. It provides a robust foundation for creating agents that can reason, plan, execute tasks, and learn from experience through advanced memory management and observability.

X-Agent Core combines cutting-edge LLM capabilities with enterprise-grade infrastructure, enabling developers to build self-hosted, auditable autonomous systems. The framework emphasizes safety, auditability, and human oversight through built-in approval workflows and comprehensive tracing.

## Project Status

- **Version**: `0.2.0-alpha` — `pyproject.toml` 为全仓版本号单一事实源
- **Status**: 商用修复中 — Phase 1「止血与架构收敛」(2026-07-19 启动), 修复 18 项 P0
- **Audit baseline**: 2026-07-19 商用交付差距审计综合评分约 31/100, 暂不具备对外商用交付条件。详见 `commercial_audit/00_商用交付差距审计报告.md` 与 [Release Readiness](./docs/operations/deployment/RELEASE_READINESS.md)
- 下方功能清单描述框架的目标能力与仓内资产; 各项能力的实际实现深度 ("宣称-存在-接通") 以上述审计复核为准

## Core Features

- **Multi-LLM Router**: Seamlessly switch between different LLM providers (OpenAI, Claude, etc.) with intelligent routing based on task requirements
- **Advanced Memory System**: Persistent graph-based memory with vector embeddings for semantic search and context retrieval
- **Workflow Orchestration**: Define, schedule, and execute complex multi-step workflows with conditional logic and error handling
- **Multi-Agent Collaboration**: Delegate tasks between agents with capability matching and load balancing
- **Browser Automation**: Integrated Playwright-based browser control for web interaction and data extraction
- **Observability & Tracing**: Full request tracing with Langfuse integration for debugging and performance monitoring
- **Approval Workflows**: Human-in-the-loop approval system for sensitive operations with audit trails
- **Policy Engine**: Define and enforce policies for agent behavior and resource access
- **PostgreSQL Persistence**: Reliable data storage with support for complex queries and transactions
- **Vector Search**: Qdrant integration for semantic similarity search and memory retrieval
- **Multi-Tenant Support**: Built-in tenant isolation and role-based access control
- **Plugin System**: Extensible plugin architecture for custom functionality
- **Cloud Sandbox Engine** *(Phase 5.5)*: Isolated code execution with Docker containerization, optional subprocess fallback, GitHub Issue→PR automation, and fire-and-forget task queuing
- **MCP Protocol Support**: Model Context Protocol integration for seamless tool discovery and management
- **CLI Tools**: Full command-line interface with REPL, interactive configuration, and workflow management

## Quick Start

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14+
- Docker and Docker Compose (optional, for containerized deployment)

### Installation

1. **Clone the repository**
   ```bash
   git clone <本仓库地址>.git
   cd X-Agent
   ```
   （本仓库暂未发布到公共托管平台；请使用内部仓库地址，或直接在本仓库目录中继续后续步骤。）

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **(Optional) Initialize the database**

   The database initializes automatically on first run — local SQLite stores are
   created lazily, so you can skip this step for a quick start. To pre-initialize
   the local store explicitly:
   ```bash
   python -c "from backend.local.migration import initialize_local_database; initialize_local_database()"
   ```

## Architecture

X-Agent Core follows a modular, layered architecture:

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                   │
│  /workflows  /agents  /tools  /memory  /approvals        │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  Core Services Layer                      │
│  LLM Router  │  Memory System  │  Policy Engine          │
│  Workflow    │  Approval       │  Audit                  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Infrastructure Layer                         │
│  PostgreSQL  │  Qdrant  │  Playwright  │  Langfuse       │
└─────────────────────────────────────────────────────────┘
```

## Documentation

- [Installation Guide](./docs/operations/setup/INSTALL.md) - Detailed setup instructions
- [Deployment Quickstart](./docs/operations/deployment/DEPLOYMENT.md) - Supported local, DeepSeek, and Docker Compose startup paths
- [Release Readiness](./docs/operations/deployment/RELEASE_READINESS.md) - Current commercial delivery status, validation commands, and production checklist
- [Contributing Guide](./CONTRIBUTING.md) - Development workflow and guidelines
- [API Documentation](./docs/developer/api/API.md) - REST API reference
- [API Error Codes](./docs/developer/api/API_ERROR_CODES.md) - Complete error code reference
- [Advanced Features](./docs/concepts/features/ADVANCED_FEATURES.md) - Workflow orchestration, multi-agent collaboration, memory system
- [Architecture Guide](./docs/concepts/architecture/ARCHITECTURE.md) - System design and components
- [Cloud Sandbox Engine](./docs/operations/deployment/PHASE_55_DEPLOYMENT.md) - Docker-based code execution, GitHub automation, API reference
- [Examples](./docs/developer/sdk/EXAMPLES.md) - Code examples and use cases
- [Runnable Examples](./examples/README.md) - Runnable example scripts
- [Documentation Index](./docs/README.md) - Complete documentation navigation (四分册总索引)

## Development

### Setting Up Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Fast correctness baseline for release-candidate checks
python scripts/release_candidate_check.py

# Full local suite with coverage (slower, environment-dependent)
pytest

# Run linter
ruff check .

# Format code
ruff format .
```

### Running Locally

```bash
# Start PostgreSQL and Qdrant (using Docker Compose)
docker-compose up -d

# Run the backend server
uvicorn backend.app.main:app --reload

# Run workflow worker
xagent-workflow-worker
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on:
- Setting up your development environment
- Git workflow and branching strategy
- Code style and standards
- Pull request process
- Issue reporting

## License

This project is licensed under the MIT License - see [LICENSE](./LICENSE) file for details.

## Support

- 问题反馈: 请通过本仓库的 Issue 渠道提交 bug 或功能请求
- 故障排除: 参见 [Troubleshooting](./docs/operations/support/TROUBLESHOOTING.md) 与 [FAQ](./docs/operations/support/FAQ.md)
- 商业支持: 参见 [SUPPORT.md](./SUPPORT.md)