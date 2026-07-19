# Integrations Guide

Complete guide to integrating X-Agent Core with third-party services and platforms.

## Table of Contents

- [Overview](#overview)
- [LLM Integrations](#llm-integrations)
- [Data Integrations](#data-integrations)
- [Communication Integrations](#communication-integrations)
- [Monitoring Integrations](#monitoring-integrations)
- [Custom Integrations](#custom-integrations)

## Overview

X-Agent Core supports integrations with various third-party services to extend functionality.

## LLM Integrations

### OpenAI

```python
from xagent.llm import OpenAIProvider

provider = OpenAIProvider(
    api_key="sk-...",
    model="gpt-4",
    temperature=0.7,
    max_tokens=2000
)

response = provider.generate("What is X-Agent?")
```

### Anthropic Claude

```python
from xagent.llm import AnthropicProvider

provider = AnthropicProvider(
    api_key="sk-ant-...",
    model="claude-3-opus",
    temperature=0.7,
    max_tokens=2000
)

response = provider.generate("What is X-Agent?")
```

### Local Models (Ollama)

```python
from xagent.llm import OllamaProvider

provider = OllamaProvider(
    base_url="http://localhost:11434",
    model="llama2"
)

response = provider.generate("What is X-Agent?")
```

## Data Integrations

### PostgreSQL

```python
from xagent.data import PostgreSQLIntegration

db = PostgreSQLIntegration(
    host="localhost",
    port=5432,
    database="xagent",
    user="xagent_user",
    password="password"
)

# Query data
results = db.query("SELECT * FROM workflows")

# Insert data
db.insert("workflows", {
    "name": "my_workflow",
    "status": "active"
})
```

### MongoDB

```python
from xagent.data import MongoDBIntegration

db = MongoDBIntegration(
    uri="mongodb://localhost:27017",
    database="xagent"
)

# Query data
results = db.find("workflows", {"status": "active"})

# Insert data
db.insert("workflows", {
    "name": "my_workflow",
    "status": "active"
})
```

### Redis

```python
from xagent.data import RedisIntegration

cache = RedisIntegration(
    host="localhost",
    port=6379,
    db=0
)

# Set value
cache.set("key", "value", ttl=3600)

# Get value
value = cache.get("key")
```

## Communication Integrations

### Slack

```python
from xagent.communication import SlackIntegration

slack = SlackIntegration(
    token="xoxb-...",
    signing_secret="..."
)

# Send message
slack.send_message(
    channel="#general",
    text="Hello from X-Agent!"
)

# Send rich message
slack.send_rich_message(
    channel="#general",
    title="X-Agent Update",
    description="Workflow completed",
    color="good"
)
```

### Email

```python
from xagent.communication import EmailIntegration

email = EmailIntegration(
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    username="your@email.com",
    password="password"
)

# Send email
email.send(
    to="recipient@email.com",
    subject="X-Agent Notification",
    body="Workflow completed successfully"
)
```

### Microsoft Teams

```python
from xagent.communication import TeamsIntegration

teams = TeamsIntegration(
    webhook_url="https://outlook.webhook.office.com/..."
)

# Send message
teams.send_message(
    title="X-Agent Update",
    text="Workflow completed",
    color="0078D4"
)
```

## Monitoring Integrations

### Langfuse

```python
from xagent.monitoring import LangfuseIntegration

langfuse = LangfuseIntegration(
    public_key="pk_...",
    secret_key="sk_..."
)

# Trace execution
with langfuse.trace("workflow_execution"):
    result = workflow.execute()
```

### Datadog

```python
from xagent.monitoring import DatadogIntegration

datadog = DatadogIntegration(
    api_key="...",
    app_key="..."
)

# Send metric
datadog.send_metric(
    metric="xagent.workflow.duration",
    value=1.5,
    tags=["workflow:my_workflow"]
)
```

### Prometheus

```python
from xagent.monitoring import PrometheusIntegration

prometheus = PrometheusIntegration(
    port=9090
)

# Record metric
prometheus.counter(
    "xagent_workflows_total",
    1,
    labels={"status": "success"}
)
```

## Custom Integrations

### Create Custom Integration

```python
from xagent.integrations import BaseIntegration

class MyServiceIntegration(BaseIntegration):
    name = "my_service"
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = MyServiceClient(api_key)
    
    def connect(self):
        """Connect to service"""
        self.client.authenticate()
    
    def disconnect(self):
        """Disconnect from service"""
        self.client.close()
    
    def execute(self, action, **kwargs):
        """Execute action"""
        if action == "get_data":
            return self.client.get_data(**kwargs)
        elif action == "post_data":
            return self.client.post_data(**kwargs)
```

### Register Custom Integration

```python
from xagent import XAgent

agent = XAgent()
agent.register_integration("my_service", MyServiceIntegration(api_key="..."))

# Use integration
result = agent.execute_integration("my_service", "get_data", id=123)
```

## Integration Examples

### Complete Workflow with Integrations

```python
from xagent import Workflow, Agent
from xagent.integrations import SlackIntegration, PostgreSQLIntegration

# Setup integrations
slack = SlackIntegration(token="xoxb-...")
db = PostgreSQLIntegration(host="localhost", database="xagent")

# Create workflow
workflow = Workflow(name="data_pipeline")

# Add steps
workflow.add_step({
    "name": "fetch_data",
    "action": "query_database",
    "params": {"query": "SELECT * FROM raw_data"}
})

workflow.add_step({
    "name": "process_data",
    "action": "process",
    "params": {"data": "${fetch_data.output}"}
})

workflow.add_step({
    "name": "save_results",
    "action": "save_to_database",
    "params": {"data": "${process_data.output}"}
})

workflow.add_step({
    "name": "notify",
    "action": "send_slack_message",
    "params": {
        "channel": "#data-pipeline",
        "text": "Data pipeline completed successfully"
    }
})

# Execute workflow
result = workflow.execute()
```

## Best Practices

1. **Authentication**: Use environment variables for credentials
2. **Error Handling**: Handle integration errors gracefully
3. **Retry Logic**: Implement retry logic for failed requests
4. **Logging**: Log integration activities
5. **Testing**: Test integrations thoroughly
6. **Security**: Validate all inputs and outputs
7. **Performance**: Monitor integration performance

## Troubleshooting

### Connection Issues

```python
# Test connection
try:
    integration.connect()
    print("Connection successful")
except Exception as e:
    print(f"Connection failed: {e}")
```

### Authentication Issues

```python
# Verify credentials
import os
api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("API_KEY not set")
```

## Additional Resources

- [Plugins Guide](./PLUGINS.md)
- [API Documentation](./API.md)
- [Examples](./EXAMPLES.md)

---

Last Updated: 2026-05-28
