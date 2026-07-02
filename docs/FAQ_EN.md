# Frequently Asked Questions (FAQ)

Common questions about X-Agent Core.

## General Questions

### What is X-Agent Core?

X-Agent Core is an open-source autonomous agent framework that enables developers to build intelligent, self-evolving systems. It combines LLM capabilities with enterprise-grade infrastructure for controlled pilot autonomous-agent deployments.

### Who should use X-Agent Core?

X-Agent Core is designed for:
- Developers building autonomous systems
- Teams implementing AI-powered workflows
- Organizations needing enterprise-grade agent infrastructure
- Researchers exploring agent architectures

### Is X-Agent Core production-ready?

X-Agent Core is designed with production-oriented architecture, but the current
commercial delivery boundary is owner-gated. This FAQ is not GA-ready,
release-ready, commercial delivery-complete, or full Codex parity evidence.

The implementation includes:
- Comprehensive error handling
- Multi-tenant support
- Audit logging and compliance
- High availability architecture
- Security best practices

### What's the license?

X-Agent Core is licensed under the MIT License, allowing free use in commercial and personal projects.

## Installation & Setup

### What are the system requirements?

- Python 3.11 or higher
- PostgreSQL 14 or higher
- 4GB RAM minimum (8GB recommended)
- 2GB disk space
- Linux, macOS, or Windows 10+

See [Installation Guide](../INSTALL.md#system-requirements) for details.

### Can I use X-Agent Core on Windows?

Yes, X-Agent Core works on Windows 10/11. We recommend using WSL2 (Windows Subsystem for Linux) for better compatibility.

### Do I need Docker?

Docker is optional but recommended for:
- Consistent development environments
- Easy deployment
- Simplified dependency management
- Multi-service orchestration

See [Docker Installation](../INSTALL.md#docker-installation) for setup instructions.

### How do I set up the development environment?

1. Clone the repository
2. Create a virtual environment
3. Install dependencies with `pip install -e ".[dev]"`
4. Configure environment variables
5. Initialize the database

See [Development Setup](./DEVELOPMENT.md) for detailed instructions.

## Features & Capabilities

### What LLM providers are supported?

X-Agent Core supports:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic Claude
- Google Gemini
- Open-source models via Ollama
- Custom LLM providers

### Can I use multiple LLM providers?

Yes, X-Agent Core includes an intelligent LLM router that can:
- Automatically select the best provider for each task
- Fall back to alternative providers on failure
- Balance cost and performance
- Route based on task requirements

### What workflow features are available?

Workflows support:
- Sequential and parallel execution
- Conditional branching
- Error handling and retries
- Compensation/rollback on failure
- Timeout management
- Resource constraints

### How does the memory system work?

The memory system provides:
- Graph-based persistent storage
- Vector embeddings for semantic search
- Automatic context retrieval
- Memory consolidation and cleanup
- Multi-level memory hierarchy

### Can I automate web interactions?

Yes, X-Agent Core includes:
- Playwright-based browser automation
- JavaScript execution
- Form filling and submission
- Data extraction
- Screenshot capture
- Cookie and session management

### Does X-Agent Core support desktop automation?

Yes, X-Agent Core supports:
- Desktop UI interaction
- Keyboard and mouse control
- Clipboard operations
- Input method control
- Window management

## Configuration & Deployment

### How do I configure X-Agent Core?

Configuration is done through:
- Environment variables (.env file)
- Configuration files (YAML/JSON)
- Runtime configuration
- Dependency injection

See [Configuration Guide](./CONFIGURATION.md) for details.

### What databases are supported?

X-Agent Core uses:
- **Primary**: PostgreSQL 14+ (required)
- **Vector DB**: Qdrant (for semantic search)
- **Cache**: Redis (optional, for performance)

### How do I deploy X-Agent Core to production?

See [Deployment Guide](./DEPLOYMENT.md) for:
- Docker deployment
- Kubernetes deployment
- Cloud platform deployment (AWS, GCP, Azure)
- On-premises deployment
- High availability setup

### How do I monitor X-Agent Core?

X-Agent Core provides:
- Request tracing with Langfuse
- Prometheus metrics
- Structured logging
- Health check endpoints
- Performance dashboards

See [Observability Guide](./OBSERVABILITY.md) for details.

## Development & Integration

### How do I create a custom agent?

```python
from x_agent import Agent

class MyAgent(Agent):
    def __init__(self):
        super().__init__()
        self.register_tool("my_tool", self.my_tool)
    
    def my_tool(self, input_data):
        # Your implementation
        return result
```

### How do I create a custom workflow?

```python
from x_agent import Workflow, Task

workflow = Workflow(
    name="my_workflow",
    tasks=[
        Task(name="step1", action="action1"),
        Task(name="step2", action="action2")
    ]
)
```

### How do I integrate with external APIs?

X-Agent Core provides:
- Built-in HTTP client
- OAuth support
- API key management
- Rate limiting
- Retry logic

### Can I extend X-Agent Core?

Yes, X-Agent Core is extensible through:
- Custom tools and actions
- Custom agents
- Custom workflows
- Plugin system
- Middleware

See [Plugin Development Guide](./PLUGIN_DEVELOPMENT_GUIDE.md) for details.

## Troubleshooting

### How do I debug issues?

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### What should I do if I encounter an error?

1. Check the error message and logs
2. Review [Troubleshooting Guide](./TROUBLESHOOTING.md)
3. Check [Common Issues](./troubleshooting/COMMON_ISSUES.md)
4. Search existing GitHub issues
5. Open a new issue with details

### How do I report a bug?

1. Check if the issue already exists
2. Provide:
   - X-Agent Core version
   - Python version
   - Operating system
   - Minimal reproduction code
   - Error logs
3. Open an issue on GitHub

### How do I request a feature?

1. Check if the feature is already requested
2. Describe the use case
3. Explain the expected behavior
4. Open a feature request on GitHub

## Performance & Optimization

### How do I improve performance?

- Use appropriate LLM models for tasks
- Optimize memory queries
- Use caching where applicable
- Parallelize independent tasks
- Monitor and profile bottlenecks

See [Performance Optimization Guide](./PERFORMANCE_OPTIMIZATION_GUIDE.md) for details.

### How do I handle large-scale deployments?

- Use load balancing
- Implement horizontal scaling
- Optimize database queries
- Use caching and CDN
- Monitor resource usage

See [Capacity Planning Guide](./CAPACITY_PLANNING_AND_RELEASE.md) for details.

## Security & Compliance

### Is X-Agent Core secure?

X-Agent Core includes:
- Input validation and sanitization
- SQL injection prevention
- CSRF protection
- Rate limiting
- Audit logging
- Encryption support

See [Security Guide](./SECURITY_GUIDE.md) for details.

### How do I ensure compliance?

X-Agent Core supports:
- Audit logging
- Data retention policies
- Access control (RBAC)
- Approval workflows
- Compliance reporting

### How do I manage secrets?

X-Agent Core supports:
- Environment variables
- Secret management services
- Encrypted configuration
- Key rotation

## Support & Community

### Where can I get help?

- **Documentation**: [docs/README.md](./README.md)
- **FAQ**: This page
- **Issues**: GitHub issues
- **Discussions**: GitHub discussions
- **Email**: support@x-agent.dev

### How do I contribute?

See [Contributing Guide](../CONTRIBUTING.md) for:
- Code contribution guidelines
- Documentation contribution
- Bug reporting
- Feature requests

### How do I stay updated?

- Watch the GitHub repository
- Subscribe to releases
- Follow our blog
- Join community discussions

---

Last Updated: 2026-05-27

For more information, see [Documentation Index](./README.md)
