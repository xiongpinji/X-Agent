"""Generate comprehensive API documentation."""

import json
from pathlib import Path
from typing import Any

from fastapi.openapi.utils import get_openapi

from backend.app.main import app


def generate_openapi_schema() -> dict[str, Any]:
    """Generate OpenAPI schema for the application."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="X-Agent API",
        version="0.1.0",
        description="""
# X-Agent API Documentation

X-Agent is an autonomous agent platform that combines LLM reasoning with tool execution,
memory management, and workflow orchestration.

## Key Features

- **Agent Execution**: Run autonomous agents with task planning and execution
- **Workflow Orchestration**: Define and execute complex workflows
- **Memory Management**: Persistent memory with semantic search
- **Browser Automation**: Automated web interaction and data extraction
- **Tool Integration**: Extensible tool system for custom capabilities
- **Audit & Compliance**: Complete audit trail and approval workflows

## Authentication

All API endpoints (except `/health` and `/ready`) require an API key:

```
X-API-Key: your-api-key
```

## Rate Limiting

API requests are rate-limited to prevent abuse:
- Default: 1000 requests per hour per API key
- Burst: 100 requests per minute

## Error Handling

All errors follow a consistent format:

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "request_id": "uuid"
}
```

## Pagination

List endpoints support pagination:

```
GET /api/v1/resource?limit=20&offset=0
```

Response includes:
- `items`: Array of resources
- `total`: Total count
- `limit`: Items per page
- `offset`: Current offset
""",
        routes=app.routes,
        tags=[
            {
                "name": "Health",
                "description": "Health check endpoints",
            },
            {
                "name": "Agents",
                "description": "Agent execution and management",
            },
            {
                "name": "Workflows",
                "description": "Workflow definition and execution",
            },
            {
                "name": "Memory",
                "description": "Memory management and retrieval",
            },
            {
                "name": "Tools",
                "description": "Tool management and execution",
            },
            {
                "name": "Audit",
                "description": "Audit trail and compliance",
            },
            {
                "name": "Users",
                "description": "User management",
            },
            {
                "name": "Tenants",
                "description": "Multi-tenant management",
            },
        ],
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API Key for authentication",
        }
    }

    # Add security to all endpoints
    openapi_schema["security"] = [{"ApiKeyHeader": []}]

    # Add common responses
    openapi_schema["components"]["responses"] = {
        "UnauthorizedError": {
            "description": "Authentication information is missing or invalid",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string"},
                            "error_code": {"type": "string"},
                        },
                    }
                }
            },
        },
        "ForbiddenError": {
            "description": "User does not have permission to access this resource",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string"},
                            "error_code": {"type": "string"},
                        },
                    }
                }
            },
        },
        "NotFoundError": {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string"},
                            "error_code": {"type": "string"},
                        },
                    }
                }
            },
        },
        "ValidationError": {
            "description": "Request validation failed",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "loc": {"type": "array"},
                                        "msg": {"type": "string"},
                                        "type": {"type": "string"},
                                    },
                                },
                            }
                        },
                    }
                }
            },
        },
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def save_openapi_schema(output_path: str = "docs/openapi.json") -> None:
    """Save OpenAPI schema to file."""
    schema = generate_openapi_schema()
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(schema, f, indent=2)

    print(f"OpenAPI schema saved to {output_file}")


def generate_markdown_docs(output_path: str = "docs/API.md") -> None:
    """Generate Markdown documentation from OpenAPI schema."""
    schema = generate_openapi_schema()
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        f.write("# X-Agent API Documentation\n\n")
        f.write(f"**Version**: {schema.get('info', {}).get('version', 'unknown')}\n\n")
        f.write(f"{schema.get('info', {}).get('description', '')}\n\n")

        # Write paths
        f.write("## Endpoints\n\n")
        paths = schema.get("paths", {})

        for path, methods in sorted(paths.items()):
            f.write(f"### {path}\n\n")

            for method, details in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    f.write(f"#### {method.upper()}\n\n")
                    f.write(f"{details.get('summary', '')}\n\n")
                    f.write(f"{details.get('description', '')}\n\n")

                    # Parameters
                    if "parameters" in details:
                        f.write("**Parameters:**\n\n")
                        for param in details["parameters"]:
                            f.write(f"- `{param['name']}` ({param.get('in', 'query')}): ")
                            f.write(f"{param.get('description', '')}\n")
                        f.write("\n")

                    # Request body
                    if "requestBody" in details:
                        f.write("**Request Body:**\n\n")
                        f.write("```json\n")
                        f.write(json.dumps(details["requestBody"], indent=2))
                        f.write("\n```\n\n")

                    # Responses
                    if "responses" in details:
                        f.write("**Responses:**\n\n")
                        for status, response in details["responses"].items():
                            f.write(f"- `{status}`: {response.get('description', '')}\n")
                        f.write("\n")

    print(f"Markdown documentation saved to {output_file}")


if __name__ == "__main__":
    save_openapi_schema()
    generate_markdown_docs()
    print("API documentation generated successfully!")
