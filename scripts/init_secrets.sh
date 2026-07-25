#!/bin/bash
# X-Agent production secrets initialization
# 首次启动自动生成生产密钥
set -e

SECRETS_FILE="/app/.generated_secrets"

if [ -z "$XAGENT_JWT_SECRET" ]; then
    export XAGENT_JWT_SECRET=$(openssl rand -hex 32)
    echo "XAGENT_JWT_SECRET=$XAGENT_JWT_SECRET" >> "$SECRETS_FILE"
    echo "[init_secrets] Generated JWT_SECRET"
fi

if [ -z "$XAGENT_ENCRYPTION_KEY" ]; then
    export XAGENT_ENCRYPTION_KEY=$(openssl rand -hex 32)
    echo "XAGENT_ENCRYPTION_KEY=$XAGENT_ENCRYPTION_KEY" >> "$SECRETS_FILE"
    echo "[init_secrets] Generated ENCRYPTION_KEY"
fi

if [ -z "$XAGENT_AUDIT_HMAC_SECRET" ]; then
    export XAGENT_AUDIT_HMAC_SECRET=$(openssl rand -hex 32)
    echo "XAGENT_AUDIT_HMAC_SECRET=$XAGENT_AUDIT_HMAC_SECRET" >> "$SECRETS_FILE"
    echo "[init_secrets] Generated AUDIT_HMAC_SECRET"
fi

echo "[init_secrets] Secrets initialized. Starting application..."
exec "$@"
