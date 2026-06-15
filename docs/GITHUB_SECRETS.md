# GitHub Secrets Configuration Guide

This document outlines all required GitHub Secrets for the X-Agent CI/CD pipeline.

## Required Secrets

### 1. Container Registry Secrets
- **GITHUB_TOKEN**: Automatically provided by GitHub Actions (no setup needed)

### 2. AWS Deployment Secrets (for staging/production)
- **AWS_ACCESS_KEY_ID**: AWS IAM access key ID
- **AWS_SECRET_ACCESS_KEY**: AWS IAM secret access key
- **AWS_REGION**: AWS region (e.g., us-east-1)

### 3. Kubernetes & Helm Secrets
- **HELM_REPO_URL**: URL to Helm repository

The Helm chart consumes these values keys:

- `secrets.databaseUrl`
- `secrets.redisUrl`
- `secrets.apiKey`
- `secrets.jwtSecret`
- `secrets.encryptionKey`
- `secrets.auditHmacSecret`
- `secrets.langfusePublicKey`
- `secrets.langfuseSecretKey`
- `secrets.sentryDsn`
- `secrets.workflowEventRabbitmqUrl`

The CI/CD workflows must pass those keys with `secrets.enabled=true`. Do not use the legacy Helm values keys `secrets.secretKey`, `secrets.dbPassword`, or `secrets.redisPassword`.

Staging:

- **STAGING_DATABASE_URL**: Staging database connection URL
- **STAGING_REDIS_URL**: Staging Redis connection URL
- **STAGING_API_KEY**: Staging API key
- **STAGING_JWT_SECRET**: Staging JWT signing secret
- **STAGING_ENCRYPTION_KEY**: Staging encryption key
- **STAGING_AUDIT_HMAC_SECRET**: Staging audit HMAC secret
- **STAGING_LANGFUSE_PUBLIC_KEY**: Staging Langfuse public key
- **STAGING_LANGFUSE_SECRET_KEY**: Staging Langfuse secret key
- **STAGING_SENTRY_DSN**: Staging Sentry DSN
- **STAGING_WORKFLOW_EVENT_RABBITMQ_URL**: Staging RabbitMQ URL for workflow event fan-out

Production:

- **PROD_DATABASE_URL**: Production database connection URL
- **PROD_REDIS_URL**: Production Redis connection URL
- **PROD_API_KEY**: Production API key
- **PROD_JWT_SECRET**: Production JWT signing secret
- **PROD_ENCRYPTION_KEY**: Production encryption key
- **PROD_AUDIT_HMAC_SECRET**: Production audit HMAC secret
- **PROD_LANGFUSE_PUBLIC_KEY**: Production Langfuse public key
- **PROD_LANGFUSE_SECRET_KEY**: Production Langfuse secret key
- **PROD_SENTRY_DSN**: Production Sentry DSN
- **PROD_WORKFLOW_EVENT_RABBITMQ_URL**: Production RabbitMQ URL for workflow event fan-out

### 4. Notification Secrets
- **SLACK_WEBHOOK**: Slack webhook URL for CI/CD notifications

## Setup Instructions

### Step 1: Navigate to GitHub Repository Settings
1. Go to your GitHub repository
2. Click on "Settings" tab
3. In the left sidebar, click "Secrets and variables" → "Actions"

### Step 2: Add Each Secret
For each secret below, click "New repository secret" and add:

#### Container Registry (Auto-configured)
```
Name: GITHUB_TOKEN
Value: (Automatically provided by GitHub)
```

#### AWS Credentials
```
Name: AWS_ACCESS_KEY_ID
Value: <your-aws-access-key-id>

Name: AWS_SECRET_ACCESS_KEY
Value: <your-aws-secret-access-key>

Name: AWS_REGION
Value: us-east-1  # or your preferred region
```

#### Kubernetes & Helm
```
Name: HELM_REPO_URL
Value: https://your-helm-repo.example.com

Name: STAGING_DATABASE_URL
Value: <staging-database-url>

Name: STAGING_REDIS_URL
Value: <staging-redis-url>

Name: STAGING_API_KEY
Value: <staging-api-key>

Name: STAGING_JWT_SECRET
Value: <staging-jwt-secret>

Name: STAGING_ENCRYPTION_KEY
Value: <staging-encryption-key>

Name: STAGING_AUDIT_HMAC_SECRET
Value: <staging-audit-hmac-secret>

Name: STAGING_LANGFUSE_PUBLIC_KEY
Value: <staging-langfuse-public-key>

Name: STAGING_LANGFUSE_SECRET_KEY
Value: <staging-langfuse-secret-key>

Name: STAGING_SENTRY_DSN
Value: <staging-sentry-dsn>

Name: STAGING_WORKFLOW_EVENT_RABBITMQ_URL
Value: <staging-rabbitmq-url>

Name: PROD_DATABASE_URL
Value: <production-database-url>

Name: PROD_REDIS_URL
Value: <production-redis-url>

Name: PROD_API_KEY
Value: <production-api-key>

Name: PROD_JWT_SECRET
Value: <production-jwt-secret>

Name: PROD_ENCRYPTION_KEY
Value: <production-encryption-key>

Name: PROD_AUDIT_HMAC_SECRET
Value: <production-audit-hmac-secret>

Name: PROD_LANGFUSE_PUBLIC_KEY
Value: <production-langfuse-public-key>

Name: PROD_LANGFUSE_SECRET_KEY
Value: <production-langfuse-secret-key>

Name: PROD_SENTRY_DSN
Value: <production-sentry-dsn>

Name: PROD_WORKFLOW_EVENT_RABBITMQ_URL
Value: <production-rabbitmq-url>
```

#### Notifications
```
Name: SLACK_WEBHOOK
Value: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Generating Secure Passwords

Use the following command to generate secure random passwords:

```bash
# Generate a 32-character random password
openssl rand -base64 32

# Or using Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Verification

After adding all secrets, verify they are correctly configured:

1. Go to "Settings" → "Secrets and variables" → "Actions"
2. You should see all secrets listed (values are hidden)
3. Run a test workflow to ensure secrets are accessible

## Security Best Practices

1. **Rotate Secrets Regularly**: Update passwords and keys every 90 days
2. **Use IAM Roles**: Prefer AWS IAM roles over access keys when possible
3. **Limit Permissions**: Grant only necessary permissions to each secret
4. **Audit Access**: Monitor who has access to secrets
5. **Never Commit Secrets**: Use `.gitignore` to prevent accidental commits

## Troubleshooting

### Secrets Not Available in Workflow
- Ensure the secret name matches exactly (case-sensitive)
- Check that the workflow file references the secret correctly: `${{ secrets.SECRET_NAME }}`
- Verify the secret is added to the correct repository (not organization-level)

### Authentication Failures
- Verify AWS credentials have correct permissions
- Check that Slack webhook URL is valid and not expired
- Ensure Helm repository URL is accessible

## References

- [GitHub Actions Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Slack Webhook Documentation](https://api.slack.com/messaging/webhooks)
