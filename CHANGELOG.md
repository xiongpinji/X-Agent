# Changelog

All notable changes to X-Agent are documented in this file.

## [Unreleased]

### Phase 5.5 - Cloud Sandbox Engine (2026-06-04)

#### Added
- **Cloud Sandbox Execution Engine**: Docker-based isolated code execution with subprocess fallback
  - `DockerSandbox` class: Container isolation with network/memory/CPU limits, read-only rootfs
  - `SandboxOrchestrator`: Persistent drain loop for task scheduling and worker coordination
  - `SandboxWorker`: Parallel task execution with priority queue management
  - `TaskQueue`: Priority-based task queuing with status tracking
  
- **Sandbox API Endpoints**:
  - `POST /api/v1/sandbox/tasks`: Fire-and-forget task submission with timeout/image/network config
  - `GET /api/v1/sandbox/tasks`: List all tasks with filtering
  - `GET /api/v1/sandbox/tasks/{task_id}`: Poll task status and results
  - `POST /api/v1/sandbox/webhook/github`: HMAC-signed GitHub issue webhook integration

- **GitHub Automation Pipeline**:
  - `GitOperations`: Clone, commit, push, branch creation with token demasking in logs
  - `GitHubWebhookHandler`: HMAC-SHA256 signature validation, constant-time comparison
  - `IssueToPRPipeline`: Complete Issue→Fix→Test→PR workflow with AgentFixRunner
  - Automatic issue assignment detection and PR creation with comments

- **Infrastructure**:
  - Docker backend detection with auto-fallback to subprocess isolation
  - Docker-out-of-Docker (DooD) support for containerized deployments
  - Dockerfile runtime updates: git installation for IssueToPR pipeline
  - requirements.txt optional docker dependency (docker>=7.0.0)

#### Security
- HMAC-SHA256 webhook verification with secret rotation support
- Sandbox:run scope enforcement for all API endpoints
- Network isolation by default (configurable per-task)
- Token demasking in task logs and audit trails

#### Tests
- 38 integration tests covering:
  - Docker container execution and subprocess fallback
  - Parallel task orchestration and priority scheduling
  - API submission, polling, and webhook verification
  - Full Issue→PR pipeline including git operations

---

## [v1.0.0-rc1] - 2026-06-01

### Phase 1-4 Complete

#### Phase 1 - MCP Protocol Enhancement
- MCP tool discovery engine with auto-registration
- MCP manager integration to FastAPI startup/shutdown lifecycle
- MCP server configuration management (YAML-based)
- Tool adapter for unified MCP client handling

#### Phase 2 - CLI Tools
- Typer-based command-line interface with 6 command modules
- Interactive REPL for agent communication
- Configuration management CLI
- Workflow command suite

#### Phase 3 - Hook System
- Extensible hook executor with fail-open semantics
- Hook configuration from `.xagent/hooks.json`
- Integration to startup lifecycle
- Type-safe hook definitions

#### Phase 4 - Context Management Enhanced
- Session recovery with distributed state management
- Code indexing for context compression
- Semantic retrieval from vector store
- Compression pipeline for token optimization

### Bug Fixes

#### LLM Backend & Tool Execution
- Fixed retry coroutine leakage in `llm_providers.py`
- Fixed schema validation for tool execution arguments
- Fixed tool name normalization across MCP and native registries
- Fixed argument parsing for complex nested tool inputs
- Fixed tool root path resolution for file operations

#### Production Infrastructure
- Fixed Dockerfile git installation (IssueToPR dependency)
- Fixed requirements.txt optional docker package declaration
- Fixed FastAPI route regex deprecation (pattern parameter)

#### Memory & Context
- Fixed memory store/retrieve interface contracts
- Fixed session recovery deadlock in non-reentrant locks
- Fixed compression regex unicode support
- Fixed code index enumeration state management

---

## Previous Releases

### [v0.9.0] - 2026-05-30
- Test suite consolidation (backend/tests → root tests/enterprise)
- Pytest collection error fixes (75 errors resolved)
- QueuePool async engine compatibility fixes
- Prometheus duplicate registry fixes
- Observability contract fixes (error envelope structure)

### [v0.8.0] - 2026-05-28
- PBKDF2HMAC security implementation
- AST-based execution sandbox
- Concurrent lock refactoring
- Random salt generation for encryption
- Authentication TTL enforcement

### [v0.7.0] - 2026-05-25
- Multi-cluster version drift fixes (57 failures)
- Starlette route API updates
- HTTPx transport parameter alignment
- SQLite executescript for multi-statement support

---

## Development Milestones

- **Q2 2026**: Phase 5.5 Cloud Sandbox (current)
- **Q3 2026**: Phase 5.6 Multi-Channel Unified Adapter
- **Q4 2026**: Production hardening and performance optimization
- **2026+**: Enterprise compliance and advanced reasoning

---

**Format**: Following [Semantic Versioning](https://semver.org/) with Phase numbering for major features.
