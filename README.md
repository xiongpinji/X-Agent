# X-Agent Core

X-Agent Core is an open-source autonomous agent framework designed for building intelligent, self-evolving systems. It provides a robust foundation for creating agents that can reason, plan, execute tasks, and learn from experience through advanced memory management and observability.

X-Agent Core combines cutting-edge LLM capabilities with enterprise-grade infrastructure, enabling developers to build production-ready autonomous systems. The framework emphasizes safety, auditability, and human oversight through built-in approval workflows and comprehensive tracing.

## Core Features

- **Multi-LLM Router**: Seamlessly switch between different LLM providers (OpenAI, Claude, etc.) with intelligent routing based on task requirements
- **Advanced Memory System**: Persistent graph-based memory with vector embeddings for semantic search and context retrieval
- **Workflow Orchestration**: Define, schedule, and execute complex multi-step workflows with conditional logic and error handling
- **Browser Automation**: Integrated Playwright-based browser control for web interaction and data extraction
- **Observability & Tracing**: Full request tracing with Langfuse integration for debugging and performance monitoring
- **Approval Workflows**: Human-in-the-loop approval system for sensitive operations with audit trails
- **Policy Engine**: Define and enforce policies for agent behavior and resource access
- **PostgreSQL Persistence**: Reliable data storage with support for complex queries and transactions
- **Vector Search**: Qdrant integration for semantic similarity search and memory retrieval
- **Multi-Tenant Support**: Built-in tenant isolation and role-based access control

## Quick Start

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14+
- Docker and Docker Compose (optional, for containerized deployment)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/x-agent/x-agent-core.git
   cd x-agent-core
   ```

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

5. **Initialize the database**
   ```bash
   python -m backend.app.core.migration init
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

- [Installation Guide](./INSTALL.md) - Detailed setup instructions
- [Contributing Guide](./CONTRIBUTING.md) - Development workflow and guidelines
- [API Documentation](./docs/API.md) - REST API reference
- [Architecture Guide](./docs/ARCHITECTURE.md) - System design and components
- [Examples](./docs/EXAMPLES.md) - Code examples and use cases

## Development

### Setting Up Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
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
uvicorn backend.app.web:app --reload

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

- GitHub Issues: [Report bugs or request features](https://github.com/x-agent/x-agent-core/issues)
- Documentation: [Full documentation](./docs/README.md)
- Email: support@x-agent.dev

## Roadmap

- Q2 2025: Multi-agent collaboration framework
- Q3 2025: Advanced reasoning with chain-of-thought
- Q4 2025: Custom model fine-tuning support
- 2026: Enterprise features (SSO, advanced audit, compliance)

---

**X-Agent Core** - Building the future of autonomous systems
