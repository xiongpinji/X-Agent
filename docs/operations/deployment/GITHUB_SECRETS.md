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
- **STAGING_SECRET_KEY**: Secret key for staging environment
- **STAGING_DB_PASSWORD**: Database password for staging
- **STAGING_REDIS_PASSWORD**: Redis password for staging

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

Name: STAGING_SECRET_KEY
Value: <generate-a-secure-random-key>

Name: STAGING_DB_PASSWORD
Value: <generate-a-secure-random-password>

Name: STAGING_REDIS_PASSWORD
Value: <generate-a-secure-random-password>
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
