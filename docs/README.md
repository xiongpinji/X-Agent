# X-Agent Core Documentation

Welcome to the X-Agent Core documentation. This is your comprehensive guide to understanding, installing, and contributing to the X-Agent Core project.

## Quick Navigation

### Getting Started

- **[README](../README.md)** - Project overview and quick start guide
- **[Installation Guide](../INSTALL.md)** - Detailed setup instructions for all platforms
- **[Quick Start](./QUICKSTART.md)** - 5-minute setup guide

### Development

- **[Contributing Guide](../CONTRIBUTING.md)** - How to contribute to the project
- **[Development Setup](./DEVELOPMENT.md)** - Detailed development environment setup
- **[Architecture Guide](./ARCHITECTURE.md)** - System design and component overview
- **[API Documentation](./API.md)** - REST API reference

### Features & Usage

- **[Workflows](./WORKFLOWS.md)** - Creating and managing workflows
- **[Memory System](./MEMORY.md)** - Understanding the memory and context system
- **[LLM Router](./LLM_ROUTER.md)** - Multi-LLM provider configuration
- **[Browser Automation](./BROWSER.md)** - Web interaction and automation
- **[Observability](./OBSERVABILITY.md)** - Tracing and monitoring
- **[Approvals](./APPROVALS.md)** - Human-in-the-loop approval workflows
- **[Policies](./POLICIES.md)** - Policy engine and constraints

### Examples & Tutorials

- **[User Guide](./user-guide/README.md)** - Product overview and core concepts
- **[Getting Started](./tutorials/GETTING_STARTED.md)** - 5-minute quick start
- **[Agent Basics](./tutorials/01-agent-basics.md)** - Agent usage tutorial
- **[Workflow Orchestration](./tutorials/02-workflow-orchestration.md)** - Workflow guide
- **[Memory System](./tutorials/03-memory-system.md)** - Memory system tutorial
- **[Browser Automation](./tutorials/04-browser-automation.md)** - Browser automation guide
- **[Examples](./examples/README.md)** - Code examples and use cases
- **[Best Practices](./best-practices/README.md)** - Best practices guide
- **[Troubleshooting](./troubleshooting/COMMON_ISSUES.md)** - Common issues and solutions
- **[FAQ](./faq/README.md)** - Frequently asked questions
- **[Video Scripts](./video-scripts/README.md)** - Video tutorial scripts

### Reference

- **[API Reference](./API.md)** - Complete API endpoint documentation
- **[Configuration](./CONFIGURATION.md)** - Environment variables and settings
- **[Database Schema](./DATABASE.md)** - PostgreSQL schema reference
- **[Changelog](../CHANGELOG.md)** - Version history and release notes
- **[License](../LICENSE)** - MIT License

## Documentation Structure

```
docs/
├── README.md                           # This file - Documentation index
├── user-guide/
│   └── README.md                      # Product overview and core concepts
├── tutorials/
│   ├── GETTING_STARTED.md             # 5-minute quick start
│   ├── 01-agent-basics.md             # Agent usage tutorial
│   ├── 02-workflow-orchestration.md   # Workflow orchestration guide
│   ├── 03-memory-system.md            # Memory system tutorial
│   └── 04-browser-automation.md       # Browser automation guide
├── best-practices/
│   └── README.md                      # Best practices guide
├── troubleshooting/
│   └── COMMON_ISSUES.md               # Common issues and solutions
├── faq/
│   └── README.md                      # Frequently asked questions
├── video-scripts/
│   └── README.md                      # Video tutorial scripts
├── QUICKSTART.md                      # 5-minute setup
├── INSTALLATION.md                    # Detailed installation
├── DEVELOPMENT.md                     # Development setup
├── ARCHITECTURE.md                    # System architecture
├── API.md                             # API reference
├── WORKFLOWS.md                       # Workflow guide
├── MEMORY.md                          # Memory system
├── LLM_ROUTER.md                      # LLM configuration
├── BROWSER.md                         # Browser automation
├── OBSERVABILITY.md                   # Tracing & monitoring
├── APPROVALS.md                       # Approval workflows
├── POLICIES.md                        # Policy engine
├── CONFIGURATION.md                   # Configuration guide
├── DATABASE.md                        # Database schema
└── TROUBLESHOOTING.md                 # Common issues
```

## Key Concepts

### Agents

Autonomous entities that can reason, plan, and execute tasks using LLMs. Agents maintain state through the memory system and can interact with external tools and services.

### Workflows

Sequences of steps that define how agents should execute tasks. Workflows support branching, error handling, and conditional logic.

### Memory

A persistent, searchable knowledge base that agents use for context and reasoning. Combines structured data (PostgreSQL) with semantic search (Qdrant).

### Tools

External services and APIs that agents can invoke. Includes browser automation, API calls, database queries, and custom integrations.

### Observability

Complete tracing and monitoring of agent execution, including request correlation, performance metrics, and error tracking.

## Common Tasks

### I want to...

- **Get started quickly** → [Quick Start](./tutorials/GETTING_STARTED.md)
- **Understand the product** → [User Guide](./user-guide/README.md)
- **Learn Agent basics** → [Agent Tutorial](./tutorials/01-agent-basics.md)
- **Learn workflow orchestration** → [Workflow Tutorial](./tutorials/02-workflow-orchestration.md)
- **Learn memory system** → [Memory Tutorial](./tutorials/03-memory-system.md)
- **Learn browser automation** → [Browser Automation Tutorial](./tutorials/04-browser-automation.md)
- **See code examples** → [Examples](../examples/README.md)
- **Follow best practices** → [Best Practices](./best-practices/README.md)
- **Troubleshoot issues** → [Troubleshooting](./troubleshooting/COMMON_ISSUES.md)
- **Find answers to common questions** → [FAQ](./faq/README.md)
- **Watch video tutorials** → [Video Scripts](./video-scripts/README.md)
- **Set up development environment** → [Development Setup](./DEVELOPMENT.md)
- **Understand the architecture** → [Architecture Guide](./ARCHITECTURE.md)
- **Contribute to the project** → [Contributing Guide](../CONTRIBUTING.md)

## System Requirements

- **Python**: 3.11 or higher
- **PostgreSQL**: 14 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Disk Space**: 2GB for installation

See [Installation Guide](../INSTALL.md#system-requirements) for detailed requirements.

## Installation Methods

### Standard Installation
```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Docker Installation
```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core
docker-compose up -d
```

See [Installation Guide](../INSTALL.md) for detailed instructions.

## Architecture Overview

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

See [Architecture Guide](./ARCHITECTURE.md) for detailed information.

## API Quick Reference

### Workflows
- `POST /api/workflows` - Create workflow
- `GET /api/workflows/{id}` - Get workflow
- `PUT /api/workflows/{id}` - Update workflow
- `DELETE /api/workflows/{id}` - Delete workflow
- `POST /api/workflows/{id}/execute` - Execute workflow

### Agents
- `POST /api/agents` - Create agent
- `GET /api/agents/{id}` - Get agent
- `POST /api/agents/{id}/run` - Run agent

### Memory
- `POST /api/memory/store` - Store memory
- `GET /api/memory/search` - Search memory
- `GET /api/memory/{id}` - Get memory item

See [API Documentation](./API.md) for complete reference.

## Support & Community

- **GitHub Issues**: [Report bugs or request features](https://github.com/x-agent/x-agent-core/issues)
- **Discussions**: [Community discussions](https://github.com/x-agent/x-agent-core/discussions)
- **Email**: dev@x-agent.dev
- **Documentation**: [Full documentation](./README.md)

## Documentation Statistics

- **User Guide**: 1 document
- **Tutorials**: 5 documents (Quick Start + 4 feature tutorials)
- **Best Practices**: 1 document (5 topics)
- **Troubleshooting**: 1 document (7 problem categories)
- **FAQ**: 1 document (32 questions)
- **Examples**: 1 document (8 examples)
- **Video Scripts**: 1 document (6 videos)

**Total**: 11 user-facing documents covering 50+ topics

## Recommended Learning Path

### Beginners (1-2 weeks)
1. Read [User Guide](./user-guide/README.md)
2. Complete [Quick Start](./tutorials/GETTING_STARTED.md)
3. Learn [Agent Basics](./tutorials/01-agent-basics.md)
4. Run [Example Code](../examples/README.md)

### Intermediate (2-4 weeks)
1. Learn [Workflow Orchestration](./tutorials/02-workflow-orchestration.md)
2. Learn [Memory System](./tutorials/03-memory-system.md)
3. Learn [Browser Automation](./tutorials/04-browser-automation.md)
4. Read [Best Practices](./best-practices/README.md)

### Advanced (4+ weeks)
1. Build complete projects
2. Optimize performance and costs
3. Implement security best practices
4. Deploy to production

## Contributing

We welcome contributions! See [Contributing Guide](../CONTRIBUTING.md) for:
- Development workflow
- Code standards
- Pull request process
- Testing guidelines

## License

X-Agent Core is licensed under the MIT License. See [LICENSE](../LICENSE) for details.

## Roadmap

- **Q2 2025**: Multi-agent collaboration framework
- **Q3 2025**: Advanced reasoning with chain-of-thought
- **Q4 2025**: Custom model fine-tuning support
- **2026**: Enterprise features (SSO, advanced audit, compliance)

See [Changelog](../CHANGELOG.md) for version history.

---

**Last Updated**: 2025-05-27
**Version**: 0.2.0
**Status**: Active Development
**Documentation Version**: Complete User Documentation System
