# CI/CD Configuration & Monitoring Setup Guide

## Overview

This guide provides step-by-step instructions for configuring GitHub Secrets, verifying the CI pipeline, and starting the monitoring stack for X-Agent.

## Prerequisites

- GitHub repository with Actions enabled
- Docker and Docker Compose installed locally
- Python 3.11+
- Make installed (for running Makefile commands)

## Part 1: Configure GitHub Secrets

### Step 1.1: Access GitHub Repository Settings

1. Navigate to your GitHub repository
2. Click **Settings** tab
3. In the left sidebar, click **Secrets and variables** → **Actions**

### Step 1.2: Add Required Secrets

Click **New repository secret** for each of the following:

#### Container Registry (Auto-configured)
```
GITHUB_TOKEN: Automatically provided by GitHub Actions
```

#### AWS Deployment Credentials (for staging/production)
```
AWS_ACCESS_KEY_ID: <your-aws-access-key>
AWS_SECRET_ACCESS_KEY: <your-aws-secret-key>
AWS_REGION: us-east-1
```

#### Kubernetes & Helm Configuration
```
HELM_REPO_URL: https://your-helm-repo.example.com
STAGING_SECRET_KEY: <generate-with: openssl rand -base64 32>
STAGING_DB_PASSWORD: <generate-with: openssl rand -base64 32>
STAGING_REDIS_PASSWORD: <generate-with: openssl rand -base64 32>
```

#### Notifications
```
SLACK_WEBHOOK: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Step 1.3: Verify Secrets Configuration

1. Go back to **Secrets and variables** → **Actions**
2. Verify all secrets are listed (values are hidden for security)
3. Secrets are now ready for use in workflows

## Part 2: Verify CI Pipeline

### Step 2.1: Install Development Dependencies

```bash
# Install all dev dependencies
make dev

# Or manually:
pip install -e ".[dev,test,monitoring]"
```

### Step 2.2: Run CI Verification Script

```bash
# Run the verification script
python scripts/verify_ci.py

# This will check:
# - Python version (3.11+)
# - All required dependencies
# - Project structure
# - Linting configuration
# - Security tools
# - Test framework
# - Docker installation
```

### Step 2.3: Run Individual CI Checks

```bash
# Run linting checks
make lint

# Run security scans
make security

# Run unit tests
make test

# Run full CI pipeline
make ci
```

### Step 2.4: Verify GitHub Actions Workflow

1. Push a commit to the `develop` branch
2. Go to **Actions** tab in GitHub
3. Click on the latest workflow run
4. Verify all stages pass:
   - Code Linting
   - Security Scanning
   - Unit & Integration Tests
   - Build Docker Image
   - Deploy to Staging (if applicable)

## Part 3: Start Monitoring Stack

### Step 3.1: Verify Monitoring Configuration

```bash
# Check if monitoring files exist
ls -la monitoring/docker-compose.monitoring.yml
ls -la monitoring/prometheus.yml
ls -la monitoring/grafana/provisioning/
```

### Step 3.2: Start Monitoring Services

```bash
# Start the monitoring stack
make monitor-start

# This will start:
# - Prometheus (metrics collection)
# - Grafana (visualization)
# - AlertManager (alerting)
# - Elasticsearch (log storage)
# - Kibana (log visualization)
# - Jaeger (distributed tracing)
# - Node Exporter (system metrics)
# - Postgres Exporter (database metrics)
# - Redis Exporter (cache metrics)
# - PostgreSQL (database)
# - Redis (cache)
# - Qdrant (vector database)
```

### Step 3.3: Verify Monitoring Stack

```bash
# Run monitoring verification script
python scripts/verify_monitoring.py

# This will check:
# - Docker and Docker Compose installation
# - Monitoring configuration files
# - Service health status
# - Grafana datasource configuration
# - Prometheus targets
```

### Step 3.4: Access Monitoring Dashboards

After successful startup, access the following services:

| Service | URL | Credentials |
|---------|-----|-------------|
| Prometheus | http://localhost:9090 | None |
| Grafana | http://localhost:3000 | admin/admin |
| AlertManager | http://localhost:9093 | None |
| Elasticsearch | http://localhost:9200 | None |
| Kibana | http://localhost:5601 | None |
| Jaeger | http://localhost:16686 | None |

### Step 3.5: Configure Grafana Dashboards

1. Open Grafana: http://localhost:3000
2. Login with admin/admin
3. Go to **Dashboards** → **Browse**
4. You should see pre-configured dashboards:
   - X-Agent Overview
   - API Performance
   - Database Metrics
   - System Metrics
   - Error Tracking

## Part 4: Monitoring Stack Management

### View Monitoring Logs

```bash
# View all monitoring service logs
make monitor-logs

# View specific service logs
docker-compose -f monitoring/docker-compose.monitoring.yml logs prometheus
docker-compose -f monitoring/docker-compose.monitoring.yml logs grafana
```

### Check Monitoring Status

```bash
# Check service status
make monitor-status

# Or manually:
docker-compose -f monitoring/docker-compose.monitoring.yml ps
```

### Stop Monitoring Stack

```bash
# Stop all monitoring services
make monitor-stop

# Clean up volumes (WARNING: deletes data)
make clean-docker
```

## Part 5: Troubleshooting

### Issue: Services not starting

**Solution:**
```bash
# Check Docker daemon
docker ps

# View detailed logs
make monitor-logs

# Restart services
make monitor-stop
make monitor-start
```

### Issue: Port already in use

**Solution:**
```bash
# Find process using port (e.g., 9090 for Prometheus)
lsof -i :9090

# Kill the process
kill -9 <PID>

# Or change port in docker-compose.monitoring.yml
```

### Issue: Grafana datasource not connecting

**Solution:**
1. Go to Grafana: http://localhost:3000
2. Click **Configuration** → **Data Sources**
3. Click **Prometheus**
4. Verify URL is: `http://prometheus:9090`
5. Click **Save & Test**

### Issue: Prometheus not scraping targets

**Solution:**
1. Check Prometheus config: `monitoring/prometheus.yml`
2. Verify service names match Docker Compose service names
3. Restart Prometheus: `docker-compose -f monitoring/docker-compose.monitoring.yml restart prometheus`
4. Check targets: http://localhost:9090/targets

## Part 6: CI/CD Pipeline Workflow

### Automatic Triggers

The CI/CD pipeline automatically runs on:

1. **Push to main/develop/release branches**
   - Runs: Lint → Security → Test → Build → Deploy

2. **Pull Requests to main/develop**
   - Runs: Lint → Security → Test

3. **Daily Schedule (2 AM UTC)**
   - Runs: Full security scan

### Manual Workflow Dispatch

To manually trigger a workflow:

1. Go to **Actions** tab
2. Select the workflow
3. Click **Run workflow**
4. Select branch and click **Run workflow**

### Monitoring Workflow Status

1. Go to **Actions** tab
2. Click on workflow run to see details
3. Click on job to see logs
4. Check **Artifacts** for test reports and coverage

## Part 7: Best Practices

### Code Quality

- Run `make lint` before committing
- Run `make format` to auto-format code
- Aim for >90% test coverage
- Fix all security warnings

### Deployment

- Always test on staging first
- Use semantic versioning for releases (v1.0.0)
- Tag releases in Git: `git tag v1.0.0`
- Monitor production after deployment

### Monitoring

- Set up Slack alerts for critical metrics
- Review logs daily in Kibana
- Check Jaeger traces for performance issues
- Monitor error rates in Grafana

## Part 8: Quick Reference

### Common Commands

```bash
# Development
make dev              # Install dev dependencies
make lint             # Run linting
make format           # Format code
make test             # Run tests
make security         # Security scans
make ci               # Full CI pipeline

# Monitoring
make monitor-start    # Start monitoring stack
make monitor-stop     # Stop monitoring stack
make monitor-logs     # View logs
make monitor-status   # Check status

# Cleanup
make clean            # Clean temp files
make clean-docker     # Clean Docker resources
make clean-all        # Full cleanup
```

### Useful URLs

- GitHub Actions: https://github.com/YOUR_ORG/x-agent/actions
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Kibana: http://localhost:5601
- Jaeger: http://localhost:16686

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review GitHub Actions logs
3. Check monitoring stack logs: `make monitor-logs`
4. Consult the project documentation in `/docs`

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Elasticsearch Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
