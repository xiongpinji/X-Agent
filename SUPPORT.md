# Support & Help

Get help with X-Agent Core. This document outlines all available support channels and resources.

## Getting Help

### Documentation

Start with our comprehensive documentation:

- **[README.md](./README.md)** - Project overview and quick start
- **[INSTALL.md](./docs/operations/setup/INSTALL.md)** - Installation and setup guide
- **[QUICKSTART.md](./docs/operations/setup/QUICKSTART_DOCS.md)** - 5-minute quick start
- **[API Documentation](./docs/developer/api/API.md)** - Complete API reference
- **[Architecture Guide](./docs/concepts/architecture/ARCHITECTURE.md)** - System design and components
- **[FAQ](./docs/operations/support/FAQ.md)** - Frequently asked questions
- **[Troubleshooting](./docs/operations/support/TROUBLESHOOTING.md)** - Common issues and solutions

### Community Support

#### GitHub

- **Issues**: Report bugs or request features
  - https://github.com/x-agent/x-agent-core/issues
  - Use issue templates for bug reports and feature requests
  - Search existing issues before creating new ones

- **Discussions**: Ask questions and discuss ideas
  - https://github.com/x-agent/x-agent-core/discussions
  - General questions and discussions
  - Show and tell your projects
  - Ideas and feedback

- **Security Advisories**: Report security vulnerabilities
  - https://github.com/x-agent/x-agent-core/security/advisories
  - Use responsible disclosure process
  - Do not create public issues for security vulnerabilities

#### Community Forum

- **URL**: https://community.x-agent.dev
- **Topics**: General discussions, best practices, use cases
- **Moderation**: Community guidelines enforced
- **Response Time**: 24-48 hours typical

#### Discord Community

- **Server**: https://discord.gg/xagent
- **Channels**:
  - #general - General discussion
  - #help - Get help from community
  - #announcements - Important announcements
  - #showcase - Share your projects
  - #development - Development discussions

### Email Support

#### Free Support

- **Email**: support@x-agent.dev
- **Response Time**: 48-72 hours
- **Scope**: General questions, documentation issues, community support

#### Priority Support

- **Email**: priority-support@x-agent.dev
- **Response Time**: 24 hours
- **Scope**: Production issues, urgent questions
- **Requires**: Active support subscription

#### Enterprise Support

- **Email**: enterprise@x-agent.dev
- **Response Time**: 4 hours (24/7)
- **Scope**: All issues, dedicated support engineer
- **Includes**: Custom SLA, training, consulting

### Office Hours

- **Schedule**: Every Tuesday and Thursday, 2-3 PM UTC
- **Format**: Live Q&A session on Zoom
- **Registration**: https://x-agent.dev/office-hours
- **Recording**: Available for registered participants

## Support Tiers

### Community (Free)

- GitHub Issues and Discussions
- Community Forum
- Email support (48-72 hours)
- Documentation access
- Community Discord

**Best for**: Open-source projects, learning, small teams

### Professional ($99/month)

- All Community features
- Priority email support (24 hours)
- Monthly office hours
- Priority issue resolution
- Early access to beta features

**Best for**: Small businesses, growing teams

### Enterprise (Custom)

- All Professional features
- 24/7 phone and email support (4-hour response)
- Dedicated support engineer
- Custom SLA
- Training and consulting
- On-premise deployment support

**Best for**: Large organizations, mission-critical deployments

## Reporting Issues

### Bug Reports

When reporting a bug, include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Exact steps to reproduce
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**:
   - OS and version
   - Python version
   - X-Agent version
   - Relevant dependencies
6. **Logs**: Error messages and logs
7. **Minimal Example**: Minimal code to reproduce

### Feature Requests

When requesting a feature:

1. **Title**: Clear, concise title
2. **Description**: Detailed description of the feature
3. **Use Case**: Why you need this feature
4. **Example**: Example of how it would be used
5. **Alternatives**: Alternative solutions you've considered

### Security Vulnerabilities

For security issues:

1. **Do NOT** create a public issue
2. **Email** security@x-agent.dev with details
3. **Include**: Affected versions, impact, proof of concept
4. **Wait**: For response before public disclosure

## Troubleshooting Guide

### Common Issues

#### Installation Issues

**Problem**: `pip install` fails with dependency conflicts

**Solution**:
```bash
# Use a fresh virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install with specific Python version
pip install --python-requires=">=3.11" -e ".[dev]"

# Check for conflicting packages
pip check
```

#### Database Connection Issues

**Problem**: Cannot connect to PostgreSQL

**Solution**:
```bash
# Test connection
psql -h localhost -U xagent_user -d xagent -c "SELECT 1;"

# Check connection string
echo $DATABASE_URL

# Verify PostgreSQL is running
sudo systemctl status postgresql
```

#### API Not Responding

**Problem**: API server not responding

**Solution**:
```bash
# Check if server is running
curl http://localhost:8000/health

# Check logs
tail -f logs/xagent.log

# Restart server
pkill -f "uvicorn"
uvicorn backend.app.web:app --reload
```

#### Memory Issues

**Problem**: Out of memory errors

**Solution**:
```bash
# Check memory usage
free -h

# Increase memory limit
export XAGENT_MAX_MEMORY=4G

# Reduce batch size
export MEMORY_BATCH_SIZE=16
```

### Performance Issues

#### Slow API Responses

**Diagnosis**:
```bash
# Check database performance
EXPLAIN ANALYZE SELECT * FROM workflows WHERE user_id = $1;

# Monitor system resources
top
htop

# Check logs for slow queries
grep "duration:" logs/xagent.log | sort -t= -k2 -rn | head
```

**Solutions**:
- Add database indexes
- Increase connection pool size
- Enable query caching
- Optimize vector search parameters

#### High Memory Usage

**Diagnosis**:
```bash
# Check memory usage
ps aux | grep python

# Profile memory
python -m memory_profiler script.py
```

**Solutions**:
- Reduce batch size
- Enable memory caching
- Implement pagination
- Clean up old data

## Learning Resources

### Tutorials

- **[Getting Started](./docs/developer/tutorials/tutorials/GETTING_STARTED.md)** - Basic setup and first workflow
- **[Agent Basics](./docs/developer/tutorials/tutorials/01-agent-basics.md)** - Creating your first agent
- **[Workflow Orchestration](./docs/developer/tutorials/tutorials/02-workflow-orchestration.md)** - Building workflows
- **[Memory System](./docs/developer/tutorials/tutorials/03-memory-system.md)** - Using the memory system
- **[Browser Automation](./docs/developer/tutorials/tutorials/04-browser-automation.md)** - Web automation

### Examples

- **[Code Examples](./docs/developer/sdk/EXAMPLES.md)** - Complete working examples
- **[API Examples](./docs/developer/api/API_EXAMPLES.md)** - API usage examples
- **[Integration Examples](./docs/developer/api/INTEGRATION_GUIDE.md)** - Third-party integrations

### Video Tutorials

- **YouTube Channel**: https://youtube.com/@xagent
- **Playlist**: X-Agent Core Getting Started
- **Topics**: Installation, basic usage, advanced features

## Contributing

Want to help improve X-Agent Core?

- **[Contributing Guide](./CONTRIBUTING.md)** - How to contribute
- **[Development Setup](./docs/operations/setup/INSTALL.md#development-setup)** - Set up development environment
- **[Code of Conduct](./CODE_OF_CONDUCT.md)** - Community guidelines

## Feedback

We value your feedback! Share your thoughts:

- **GitHub Issues**: Feature requests and bug reports
- **Discussions**: Ideas and feedback
- **Email**: feedback@x-agent.dev
- **Survey**: https://x-agent.dev/feedback

## Status & Incidents

### System Status

- **Status Page**: https://status.x-agent.dev
- **Incidents**: Real-time incident updates
- **Maintenance**: Scheduled maintenance notifications
- **Subscribe**: Get status updates via email or Slack

### Incident Reports

- **Archive**: https://status.x-agent.dev/incidents
- **Postmortems**: Root cause analysis for major incidents
- **Lessons Learned**: Improvements from incidents

## FAQ

### General Questions

**Q: Is X-Agent Core free?**
A: Yes, X-Agent Core is open-source and free to use under the MIT License.

**Q: Can I use X-Agent Core in production?**
A: Yes, X-Agent Core is production-ready. See [Deployment Guide](./docs/operations/deployment/DEPLOYMENT_DETAILED.md) for production setup.

**Q: What are the system requirements?**
A: See [Installation Guide](./docs/operations/setup/INSTALL.md#system-requirements) for detailed requirements.

**Q: How do I report a security vulnerability?**
A: Email security@x-agent.dev with details. See [Security Policy](./docs/admin/security/SECURITY_GUIDE.md) for more information.

### Technical Questions

**Q: How do I configure multiple LLM providers?**
A: See [Configuration Guide](./docs/operations/setup/CONFIG_MANAGEMENT.md) for LLM setup.

**Q: How do I optimize database performance?**
A: See [Performance Guide](./docs/operations/monitoring/PERFORMANCE.md) for optimization tips.

**Q: How do I integrate with third-party services?**
A: See [Integration Guide](./docs/developer/api/INTEGRATION_GUIDE.md) for integration examples.

For more FAQs, see [FAQ.md](./docs/operations/support/FAQ.md).

## Contact Information

- **General**: info@x-agent.dev
- **Support**: support@x-agent.dev
- **Security**: security@x-agent.dev
- **Business**: business@x-agent.dev
- **Twitter**: @xagent_dev
- **GitHub**: https://github.com/x-agent/x-agent-core

## Additional Resources

- **Blog**: https://blog.x-agent.dev
- **Documentation**: https://docs.x-agent.dev
- **Community**: https://community.x-agent.dev
- **GitHub**: https://github.com/x-agent/x-agent-core

---

**Last Updated**: 2026-05-28
