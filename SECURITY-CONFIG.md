# X-Agent Security Configuration Guide

## Overview

This guide explains how to configure X-Agent with the new security hardening features implemented in the latest release.

## 1. CORS Configuration

### Development Mode
```bash
XAGENT_CORS_ORIGINS=http://localhost:3000,http://localhost:8000
XAGENT_APP_MODE=development
```

### Production Mode
```bash
XAGENT_CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
XAGENT_APP_MODE=production
```

**Important**: In production mode, wildcard CORS (`*`) is automatically rejected and replaced with safe defaults.

## 2. JWT and Encryption Keys

### Generating Strong Keys

```bash
# Generate JWT secret (64-character hex string)
XAGENT_JWT_SECRET=$(openssl rand -hex 32)

# Generate encryption key (32-character hex string)
XAGENT_ENCRYPTION_KEY=$(openssl rand -hex 16)
```

### Configuration
```bash
# .env file
XAGENT_JWT_SECRET=your-64-char-hex-string
XAGENT_ENCRYPTION_KEY=your-32-char-hex-string
XAGENT_APP_MODE=production
```

**Validation Rules**:
- Development mode: Any value accepted
- Production mode:
  - Minimum 32 characters
  - Cannot be default placeholder values
  - Must be cryptographically random

## 3. Redis Session Storage

### Optional Setup (Recommended for Production)

#### Install Redis
```bash
# macOS
brew install redis

# Ubuntu/Debian
sudo apt-get install redis-server

# Docker
docker run -d -p 6379:6379 redis:latest
```

#### Configure X-Agent
```bash
# .env file
XAGENT_REDIS_URL=redis://localhost:6379/0
```

#### Verify Connection
```bash
redis-cli ping
# Should return: PONG
```

### Fallback Behavior
If Redis is not available or not configured:
- Sessions fall back to in-memory storage
- Suitable for single-instance deployments
- Not recommended for production multi-instance setups

## 4. API Key Migration

### Prerequisites
- PostgreSQL database running
- Migration script: `backend/app/migrations/migrate_api_keys.py`
- Existing API keys in `data/api_keys.json`

### Migration Steps

1. **Backup existing keys**:
```bash
cp data/api_keys.json data/api_keys.json.backup
```

2. **Run migration**:
```bash
python -m backend.app.migrations.migrate_api_keys \
  data/api_keys.json \
  postgresql://user:password@localhost:5432/xagent
```

3. **Verify migration**:
```bash
# Check database
psql postgresql://user:password@localhost:5432/xagent
SELECT COUNT(*) FROM api_keys;
```

4. **Monitor logs**:
```bash
# Watch for any migration errors
tail -f logs/xagent.log | grep -i "migration\|api_key"
```

### Rollback (if needed)
```bash
# Restore from backup
cp data/api_keys.json.backup data/api_keys.json

# Drop database table (if needed)
psql postgresql://user:password@localhost:5432/xagent
DROP TABLE api_keys;
```

## 5. Default Credentials

### Updated Defaults
All default credentials in `.env.example` have been updated:

```bash
# Before (INSECURE)
NEO4J_PASSWORD=xagent123
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin

# After (SECURE)
NEO4J_PASSWORD=neo4j_prod_$(openssl rand -hex 16)
S3_ACCESS_KEY=s3_access_$(openssl rand -hex 16)
S3_SECRET_KEY=s3_secret_$(openssl rand -hex 16)
```

### Production Checklist
- [ ] Change all default passwords
- [ ] Use strong random values (minimum 32 characters)
- [ ] Store secrets in secure vault (e.g., HashiCorp Vault, AWS Secrets Manager)
- [ ] Never commit secrets to version control
- [ ] Rotate secrets regularly

## 6. Environment Setup Examples

### Local Development
```bash
# .env
XAGENT_APP_MODE=development
XAGENT_CORS_ORIGINS=http://localhost:3000,http://localhost:8000
XAGENT_JWT_SECRET=dev-secret-12345
XAGENT_ENCRYPTION_KEY=dev-key-12345
XAGENT_DATABASE_URL=sqlite:///./data/xagent.db
# Redis optional for development
```

### Staging Environment
```bash
# .env
XAGENT_APP_MODE=production
XAGENT_CORS_ORIGINS=https://staging.yourdomain.com
XAGENT_JWT_SECRET=$(openssl rand -hex 32)
XAGENT_ENCRYPTION_KEY=$(openssl rand -hex 16)
XAGENT_DATABASE_URL=postgresql://user:pass@postgres:5432/xagent
XAGENT_REDIS_URL=redis://redis:6379/0
```

### Production Environment
```bash
# .env (use secrets manager in production)
XAGENT_APP_MODE=production
XAGENT_CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
XAGENT_JWT_SECRET=<from-secrets-manager>
XAGENT_ENCRYPTION_KEY=<from-secrets-manager>
XAGENT_DATABASE_URL=<from-secrets-manager>
XAGENT_REDIS_URL=<from-secrets-manager>
XAGENT_NEO4J_PASSWORD=<from-secrets-manager>
XAGENT_S3_ACCESS_KEY=<from-secrets-manager>
XAGENT_S3_SECRET_KEY=<from-secrets-manager>
```

## 7. Troubleshooting

### CORS Errors
```
Error: Access to XMLHttpRequest blocked by CORS policy
```

**Solution**:
1. Check `XAGENT_CORS_ORIGINS` includes your frontend domain
2. Verify frontend is using correct protocol (http/https)
3. Check browser console for exact origin being blocked
4. Update `.env` and restart server

### JWT Secret Validation Error
```
ValueError: Production secrets must be changed from defaults
```

**Solution**:
1. Generate new secret: `openssl rand -hex 32`
2. Update `XAGENT_JWT_SECRET` in `.env`
3. Ensure `XAGENT_APP_MODE=production`
4. Restart application

### Redis Connection Error
```
Failed to initialize Redis: Connection refused
```

**Solution**:
1. Verify Redis is running: `redis-cli ping`
2. Check `XAGENT_REDIS_URL` is correct
3. Verify network connectivity to Redis server
4. Application will fall back to in-memory storage (not recommended for production)

### API Key Migration Failure
```
Failed to migrate key: duplicate key value violates unique constraint
```

**Solution**:
1. Check if keys already migrated: `SELECT COUNT(*) FROM api_keys;`
2. If table exists, drop it: `DROP TABLE api_keys;`
3. Re-run migration script
4. Check logs for detailed error messages

## 8. Security Best Practices

### Secrets Management
- Use environment variables, not hardcoded values
- Use secrets manager (Vault, AWS Secrets Manager, etc.)
- Rotate secrets regularly (quarterly minimum)
- Never commit `.env` files to version control

### CORS Configuration
- Use specific domains, never wildcard in production
- Include both http and https if needed
- Update when adding new frontend domains
- Review quarterly for unused origins

### Session Management
- Use Redis in production for distributed sessions
- Set appropriate TTLs for tokens
- Monitor token revocation logs
- Implement session timeout policies

### Database Security
- Use strong passwords (minimum 32 characters)
- Enable SSL/TLS for database connections
- Restrict database access to application servers only
- Regular backups and disaster recovery testing

## 9. Monitoring & Logging

### Key Metrics to Monitor
```bash
# Redis connection status
redis-cli INFO stats

# Database connection pool
SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;

# Token operations
grep -i "token\|auth" logs/xagent.log

# CORS violations
grep -i "cors" logs/xagent.log
```

### Alert Thresholds
- Redis connection failures: Alert immediately
- Failed authentication attempts: Alert if > 10/minute
- CORS violations: Alert if > 5/minute
- Database connection pool exhaustion: Alert immediately

## 10. Compliance & Auditing

### Security Audit Checklist
- [ ] CORS configured for production domains only
- [ ] JWT secrets are strong and randomized
- [ ] Encryption keys are strong and randomized
- [ ] API keys migrated to database
- [ ] Redis configured for session storage
- [ ] All default credentials changed
- [ ] Secrets stored in secure vault
- [ ] Access logs enabled and monitored
- [ ] Regular security updates applied
- [ ] Penetration testing completed

### Compliance Standards
- OWASP Top 10: Addresses A01:2021 - Broken Access Control
- CWE-434: Unrestricted Upload of File with Dangerous Type
- CWE-798: Use of Hard-Coded Credentials
- CWE-352: Cross-Site Request Forgery (CSRF)

---

For more information, see `security-fixes-report.md`
