# Security Policy

## Overview

X-Agent is an enterprise-grade autonomous agent framework. Security is a critical concern for all deployments. This policy outlines how we handle security vulnerabilities and maintain system security.

## Supported Versions

| Version | Released   | Support Ends | LTS | Security Updates |
|---------|------------|--------------|-----|------------------|
| 1.0.x   | 2026-06-13 | 2027-06-13   | ✓   | ✓ Critical + High |
| 0.9.x   | 2026-04-15 | 2026-09-13   |     | ✓ Critical only   |
| 0.8.x   | 2026-02-01 | 2026-05-01   |     | End of Support    |

- **LTS versions** receive security updates and critical fixes for 2 years
- **Regular versions** receive security updates for 6 months
- **End of Support:** No further updates or patches

We **strongly recommend** upgrading to the latest LTS release for production deployments.

## Security Features

### Authentication & Authorization

- **OAuth2/SSO:** GitHub, Google, and OIDC-compatible providers
- **Role-Based Access Control (RBAC):** admin, developer, viewer roles with scope enforcement
- **Session Management:** 24h token TTL, 90d refresh token expiry
- **API Key Authentication:** Scoped API keys for programmatic access with audit logging

### Data Protection

- **TLS/SSL:** All network communication encrypted (enforced for production)
- **At-Rest Encryption:** AES-256 for sensitive data in PostgreSQL
- **Secret Management:** Automatic secret rotation on first install
- **HMAC Audit Trail:** All admin actions verified with HMAC-SHA256 signatures

### Input Validation & Sanitization

- **Regex-based XSS/Injection Protection:** All user inputs validated and sanitized
- **SQL Injection Prevention:** Parameterized queries via SQLAlchemy ORM + asyncpg
- **Command Injection Prevention:** Subprocess isolation with shlex parsing
- **Schema Validation:** Pydantic models with strict type checking

### Infrastructure Security

- **Code Sandbox:** OS-level process isolation for agent execution (no untrusted code in main process)
- **Docker Isolation:** Optional container-based sandboxing for additional hardening
- **Rate Limiting:** Distributed Redis-backed rate limiting to prevent abuse
- **DDoS Mitigation:** Configurable connection limits and request size limits

### Compliance

- **GDPR-Ready:** Data export/deletion endpoints for user privacy
- **SOC 2:** Audit logging and access controls
- **HIPAA-Compatible:** Encryption at rest/in-transit, audit trails (requires additional configuration)

## Reporting Security Vulnerabilities

**Do not** open a public GitHub issue for security vulnerabilities.

### Responsible Disclosure Process

1. **Report via Email**
   - Email: security@your-org.com
   - PGP key available at: https://your-org.com/security.asc
   - Include:
     - Vulnerability description
     - Steps to reproduce
     - Affected versions
     - Suggested fix (optional)
     - Your contact information (optional)

2. **Response Timeline**
   - **48 hours:** Acknowledge receipt and verify vulnerability
   - **7 days:** Provide initial assessment and timeline
   - **30 days:** Release security patch (or explain delay)
   - **60 days:** Public disclosure announcement

3. **Coordinated Disclosure**
   - We will:
     - Develop fix on private branch
     - Create security advisories
     - Prepare release notes
     - Coordinate with users before public disclosure
   - Contributors receive:
     - Security advisory credit
     - CVE assignment support
     - Public acknowledgment (if desired)

4. **Example Report**
   ```
   Subject: Security Vulnerability: Potential SQL Injection in /api/v1/agents

   Description:
   The /api/v1/agents?name=X endpoint is vulnerable to SQL injection via
   the name parameter. Unsanitized input is directly interpolated into
   the SQL query.

   Reproduction:
   1. POST /api/v1/agents with name="'; DROP TABLE agents; --"
   2. Database table is dropped

   Affected Versions: 1.0.0-rc1 through 1.0.0

   Suggested Fix:
   Use parameterized queries (SQLAlchemy already supports this).

   Contact: your-email@example.com
   ```

## Security Configuration

### Production Deployment Checklist

```bash
# 1. Mandatory environment variables
export REQUIRE_API_KEY=true
export JWT_SECRET=$(openssl rand -hex 32)
export HMAC_SECRET=$(openssl rand -hex 32)
export DATABASE_URL="postgresql://..."

# 2. Enable TLS
export API_HTTPS_ENABLED=true
export API_TLS_CERT_PATH="/etc/ssl/certs/server.crt"
export API_TLS_KEY_PATH="/etc/ssl/private/server.key"

# 3. Configure RBAC
export RBAC_ENABLED=true
export DEFAULT_ROLE="viewer"  # Most restrictive default

# 4. Enable audit logging
export AUDIT_LOGGING_ENABLED=true
export AUDIT_LOG_DESTINATION="postgresql"

# 5. Configure rate limiting
export RATE_LIMIT_ENABLED=true
export RATE_LIMIT_REQUESTS_PER_MINUTE=600  # Adjust per deployment

# 6. Restrict API access
export API_ALLOWED_ORIGINS="https://yourdomain.com"
export API_CORS_ALLOWED_METHODS="GET,POST"

# 7. Enable CSRF protection
export CSRF_PROTECTION_ENABLED=true

# 8. Configure secure headers
export SECURE_HEADERS_ENABLED=true
export HSTS_MAX_AGE=31536000  # 1 year

# 9. Sandbox configuration
export SANDBOX_ENABLED=true
export SANDBOX_ISOLATION_LEVEL="strict"
export SANDBOX_MEMORY_LIMIT_MB=512

# 10. Monitoring & alerting
export PROMETHEUS_ENABLED=true
export ALERTMANAGER_ENABLED=true
```

### Secrets Management

```bash
# Automatic generation on first start
# Stored in: .xagent/secrets.yaml (local) or AWS Secrets Manager (production)

# Rotate secrets annually
xagent secrets rotate --all

# Audit secret access
xagent audit secrets --last-7-days
```

## Known Security Limitations

### Current Version (1.0.x)

1. **Web Search Tool** — External API calls are not encrypted end-to-end
   - Mitigation: Use on trusted networks only; sensitive queries should not use web search

2. **Browser Automation** — Headless browser state not isolated between agents
   - Mitigation: Run multiple browser instances in separate containers

3. **Agent Memory** — Graph memory edges are not encrypted at rest
   - Mitigation: Enable PostgreSQL Transparent Data Encryption (TDE)

### Planned Mitigations

- v1.1: End-to-end encryption for web search results
- v1.2: Per-agent browser instance isolation
- v1.3: Native memory encryption at rest

## Security Best Practices

### For Deployment

1. **Use xagent-lite for development only** — Always use full deployment with PostgreSQL/Redis for production
2. **Enable all security features** — Don't disable CSRF, rate limiting, or RBAC in production
3. **Require API keys** — Set `REQUIRE_API_KEY=true`
4. **Use OAuth2/SSO** — Avoid storing passwords; federate to GitHub/Google
5. **Rotate secrets regularly** — At least annually
6. **Monitor audit logs** — Set up alerts for privilege escalation, failed auth, etc.
7. **Patch promptly** — Apply security updates within 7 days of release
8. **Network isolation** — Only expose API behind WAF/load balancer
9. **Backup securely** — Encrypt database backups; store in separate secure location
10. **Test disaster recovery** — Annual DR drills to ensure backup integrity

### For Skill Development

1. **Validate all inputs** — Assume user input is hostile
2. **Use parameterized queries** — Never interpolate strings into SQL
3. **Avoid eval/exec** — Never execute untrusted code
4. **Limit subprocess calls** — Use allowlists for commands
5. **Handle errors securely** — Don't leak sensitive information in error messages
6. **Log security events** — Track authentication, authorization, data access
7. **Use secure defaults** — Default to most restrictive permissions
8. **Follow OWASP guidelines** — Review OWASP Top 10 regularly

### For API Usage

1. **Scope API keys** — Create separate keys for different operations
2. **Rotate API keys** — At least quarterly
3. **Use HTTPS only** — Never send API keys over HTTP
4. **Store secrets safely** — Use environment variables or secret managers
5. **Audit API access** — Monitor logs for unusual patterns
6. **Rate limit requests** — Respect rate limits and implement backoff
7. **Validate responses** — Verify cryptographic signatures on sensitive responses

## Incident Response

In the event of a security breach:

1. **Immediate Actions (Within 1 hour)**
   - Isolate affected systems from network
   - Preserve evidence (logs, memory dumps)
   - Contact security team: security@your-org.com
   - If data compromised, notify affected users

2. **Investigation (Within 24 hours)**
   - Determine scope (data, systems, users affected)
   - Identify root cause
   - Assess impact (CIA: Confidentiality, Integrity, Availability)
   - Create incident timeline

3. **Remediation (Within 48-72 hours)**
   - Deploy fix or workaround
   - Test fix in staging before production
   - Communicate with users (if public breach)
   - Update security documentation

4. **Post-Incident (Within 1 week)**
   - Conduct post-mortem
   - Implement preventative measures
   - Update runbooks and playbooks
   - Track lessons learned

## Security Advisories

Subscribe to security advisories:

- **GitHub:** Watch releases on https://github.com/your-org/X-Agent
- **Email:** security-announcements@your-org.com
- **Twitter:** @YourOrgSecurity

## Contact & Support

- **Security Reports:** security@your-org.com
- **General Inquiries:** support@your-org.com
- **Emergency:** +1-XXX-XXX-XXXX (security team on-call)
- **PGP Key:** https://your-org.com/security.asc

---

**Last Updated:** 2026-06-13  
**Version:** 1.0  
**Status:** Active
