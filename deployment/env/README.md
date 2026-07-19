# X-Agent Environment Configuration Files

## Development Environment (.env.development)

```bash
# Database
DB_USER=xagent
DB_PASSWORD=xagent_dev
DB_NAME=xagent_db
DB_PORT=5432

# Redis
REDIS_PASSWORD=redis_dev
REDIS_PORT=6379

# Qdrant
QDRANT_API_KEY=qdrant_dev_key
QDRANT_PORT=6333

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_dev
NEO4J_PORT=7687

# Application
ENVIRONMENT=development
LOG_LEVEL=DEBUG
DEBUG=true
SECRET_KEY=dev-secret-key-change-in-production
API_WORKERS=1
API_PORT=8000

# LLM
XAGENT_LLM_BACKEND=mock
XAGENT_ENABLE_HIGH_RISK_TOOLS=false
```

## Staging Environment (.env.staging)

```bash
# Database
DB_USER=xagent
DB_PASSWORD=staging_secure_password_here
DB_NAME=xagent_db
DB_PORT=5432

# Redis
REDIS_PASSWORD=staging_secure_password_here
REDIS_PORT=6379

# Qdrant
QDRANT_API_KEY=staging_secure_key_here
QDRANT_PORT=6333

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=staging_secure_password_here
NEO4J_PORT=7687

# Application
ENVIRONMENT=staging
LOG_LEVEL=INFO
DEBUG=false
SECRET_KEY=staging_secure_secret_key_here
API_WORKERS=2
API_PORT=8000

# LLM
XAGENT_LLM_BACKEND=openai
XAGENT_ENABLE_HIGH_RISK_TOOLS=false
```

## Production Environment (.env.production)

```bash
# Database
DB_USER=xagent
DB_PASSWORD=production_very_secure_password_here
DB_NAME=xagent_db
DB_PORT=5432

# Redis
REDIS_PASSWORD=production_very_secure_password_here
REDIS_PORT=6379

# Qdrant
QDRANT_API_KEY=production_very_secure_key_here
QDRANT_PORT=6333

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=production_very_secure_password_here
NEO4J_PORT=7687

# Application
ENVIRONMENT=production
LOG_LEVEL=WARNING
DEBUG=false
SECRET_KEY=production_very_secure_secret_key_here
API_WORKERS=4
API_PORT=8000

# LLM
XAGENT_LLM_BACKEND=openai
XAGENT_ENABLE_HIGH_RISK_TOOLS=false

# Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
```
