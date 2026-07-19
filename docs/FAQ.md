# Frequently Asked Questions (FAQ)

Common questions about X-Agent Core.

## General Questions

### What is X-Agent Core?

X-Agent Core is an open-source autonomous agent framework that enables developers to build intelligent, self-evolving systems. It combines LLM capabilities with enterprise-grade infrastructure for production-ready autonomous agents.

### Who should use X-Agent Core?

X-Agent Core is designed for:
- Developers building autonomous systems
- Teams implementing AI-powered workflows
- Organizations needing enterprise-grade agent infrastructure
- Researchers exploring agent architectures

### Is X-Agent Core production-ready?

Yes, X-Agent Core is designed for production use with:
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
- Easy database setup
- Consistent development environment
- Production deployment
- Testing

You can install PostgreSQL and Qdrant manually if preferred.

### How do I upgrade X-Agent Core?

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -e ".[dev]" --upgrade

# Run migrations
python -m backend.app.core.migration init
```

### Can I use X-Agent Core with an existing PostgreSQL database?

Yes, you can configure the connection string:

```bash
# In .env
DATABASE_URL=postgresql://user:password@your-host:5432/your-db
```

## Features & Capabilities

### What LLM providers are supported?

Currently supported:
- OpenAI (GPT-4, GPT-3.5 Turbo)
- Anthropic (Claude models)

Adding new providers is straightforward - see [Architecture Guide](./ARCHITECTURE.md#extension-points).

### Can I use multiple LLM providers simultaneously?

Yes, the LLM Router supports:
- Automatic provider selection
- Fallback strategies
- Load balancing
- Cost optimization

### What can agents do?

Agents can:
- Reason and plan using LLMs
- Execute workflows with multiple steps
- Interact with web browsers
- Search and retrieve information
- Store and recall memories
- Request human approval for sensitive actions
- Integrate with external APIs and tools

### How does the memory system work?

X-Agent Core uses a dual-layer memory system:

1. **Structured Memory (PostgreSQL)**: Facts, relationships, and structured data
2. **Vector Memory (Qdrant)**: Semantic embeddings for similarity search

This enables both precise queries and semantic understanding.

### Can I use X-Agent Core for real-time applications?

Yes, X-Agent Core supports:
- Streaming LLM responses
- WebSocket connections (planned)
- Real-time workflow execution
- Event-driven architecture

### How do I add custom tools?

Implement the `Tool` interface:

```python
class CustomTool(Tool):
    def execute(self, **kwargs):
        # Your implementation
        pass
```

See [Examples](./EXAMPLES.md) for detailed examples.

## Development

### How do I set up a development environment?

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
docker-compose up -d
python -m backend.app.core.migration init
```

See [Installation Guide](../INSTALL.md#development-setup) for details.

### How do I run tests?

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_api.py::test_create_workflow

# Run with coverage
pytest --cov=backend
```

### What code style should I follow?

X-Agent Core uses:
- PEP 8 style guide
- Ruff for linting and formatting
- Type hints for function signatures
- Google-style docstrings

Run `ruff check .` and `ruff format .` before committing.

### How do I contribute?

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linter
5. Submit a pull request

See [Contributing Guide](../CONTRIBUTING.md) for detailed instructions.

### Can I use X-Agent Core in my commercial project?

Yes, the MIT License allows commercial use. You must include the license notice in your project.

## Performance & Scalability

### How many workflows can X-Agent Core handle?

X-Agent Core can handle:
- Thousands of concurrent workflows
- Millions of memory items
- Horizontal scaling with multiple servers
- Load balancing across instances

Performance depends on your infrastructure and workflow complexity.

### How do I optimize performance?

1. **Database**: Add indexes, use connection pooling
2. **Caching**: Enable Redis caching
3. **LLM**: Use cheaper models for simple tasks
4. **Batch Processing**: Process multiple items together
5. **Monitoring**: Track and optimize slow queries

See [Troubleshooting Guide](./TROUBLESHOOTING.md#slow-performance) for details.

### What's the maximum workflow execution time?

There's no hard limit, but:
- Default timeout: 30 minutes
- Configurable per workflow
- Long-running tasks should use background workers

### How do I handle large-scale deployments?

Use Kubernetes with:
- Multiple API pods
- Multiple worker pods
- PostgreSQL replication
- Qdrant clustering
- Load balancing

See [Architecture Guide](./ARCHITECTURE.md#kubernetes-deployment) for details.

## Security

### Is X-Agent Core secure?

X-Agent Core includes:
- API key and JWT authentication
- Role-based access control (RBAC)
- Input validation and sanitization
- Encrypted credential storage
- Comprehensive audit logging
- CORS configuration

See [Security Audit Report](../backend/SECURITY_AUDIT_REPORT.md) for details.

### How do I secure API keys?

1. Use environment variables (never commit keys)
2. Rotate keys regularly
3. Use different keys for different environments
4. Restrict key permissions
5. Monitor key usage

### Can I use X-Agent Core in regulated industries?

Yes, X-Agent Core supports:
- Audit logging for compliance
- Data encryption
- Access control
- Multi-tenant isolation
- Compliance reporting

Consult with your compliance team for specific requirements.

### How do I report security issues?

Please email security@x-agent.dev with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

Do not open public issues for security vulnerabilities.

## Troubleshooting

### Why is my workflow slow?

Common causes:
1. LLM latency (check model and provider)
2. Database queries (add indexes)
3. Memory search (optimize embeddings)
4. Network latency (check connectivity)

See [Troubleshooting Guide](./TROUBLESHOOTING.md#slow-performance).

### Why am I getting "Connection refused" errors?

Check if services are running:
```bash
# PostgreSQL
psql -U postgres -h localhost

# Qdrant
curl http://localhost:6333/health

# API
curl http://localhost:8000/health
```

### Why are my tests failing?

Common causes:
1. Test database not initialized
2. Services not running
3. Missing environment variables
4. Timeout issues

See [Troubleshooting Guide](./TROUBLESHOOTING.md#testing-issues).

### How do I debug issues?

1. Enable debug logging: `DEBUG=true`
2. Check application logs: `docker-compose logs`
3. Use verbose output: `pytest -vv -s`
4. Check database: `psql -U xagent -d xagent_db`
5. Monitor resources: `top`, `docker stats`

## API & Integration

### How do I authenticate API requests?

Use API key or JWT token:

```bash
# API Key
curl -H "X-API-Key: your-key" http://localhost:8000/api/workflows

# JWT Token
curl -H "Authorization: Bearer your-token" http://localhost:8000/api/workflows
```

### What's the API rate limit?

Default: 1000 requests per hour per API key

Check response headers:
- `X-RateLimit-Limit`: Request limit
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset time

### Can I use X-Agent Core with my existing tools?

Yes, you can:
1. Create custom tools implementing the `Tool` interface
2. Integrate with REST APIs
3. Use webhooks for notifications
4. Connect to databases and services

See [Examples](./EXAMPLES.md) for integration examples.

### How do I monitor X-Agent Core?

Use:
- Langfuse for trace visualization
- Prometheus for metrics
- ELK stack for logging
- Custom dashboards

See [Observability Guide](./OBSERVABILITY.md) for details.

## Roadmap & Future

### What's planned for future releases?

- Q2 2025: Multi-agent collaboration
- Q3 2025: Advanced reasoning (chain-of-thought)
- Q4 2025: Custom model fine-tuning
- 2026: Enterprise features (SSO, advanced audit)

See [Changelog](../CHANGELOG.md) for details.

### Can I request a feature?

Yes, please:
1. Check [GitHub Issues](https://github.com/x-agent/x-agent-core/issues)
2. Create a new issue with detailed description
3. Discuss with the community
4. Consider contributing the feature

### How often are releases?

X-Agent Core follows semantic versioning:
- Patch releases: Bug fixes (as needed)
- Minor releases: New features (monthly)
- Major releases: Breaking changes (quarterly)

## Support & Community

### Where can I get help?

- **Documentation**: [Full docs](./README.md)
- **GitHub Issues**: [Report bugs](https://github.com/x-agent/x-agent-core/issues)
- **Discussions**: [Community chat](https://github.com/x-agent/x-agent-core/discussions)
- **Email**: support@x-agent.dev

### How do I stay updated?

- Watch the GitHub repository
- Subscribe to releases
- Follow on social media
- Join community discussions

### Can I contribute to documentation?

Yes! Documentation contributions are welcome:
1. Fork the repository
2. Edit documentation files
3. Submit a pull request
4. We'll review and merge

### Is there a community forum?

Yes, join our [GitHub Discussions](https://github.com/x-agent/x-agent-core/discussions) for:
- Questions and answers
- Feature discussions
- Best practices
- Community projects

---

**Still have questions?** Contact us at support@x-agent.dev or open an issue on GitHub.
