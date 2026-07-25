# Architecture Guide

Comprehensive overview of X-Agent Core's system design and components.

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                   │
│  /workflows  /agents  /tools  /memory  /approvals        │
│  /evolution  /metrics  /ops    /auth   /tenants          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  Core Services Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ LLM Router   │  │ Memory Sys   │  │ Policy Eng   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Workflow Eng │  │ Approval Sys │  │ Audit Trail  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Infrastructure Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │PostgreSQL│  │ Qdrant   │  │Playwright│  │Langfuse  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. API Layer (FastAPI)

**Location**: `backend/app/api/`

Provides REST endpoints for all system operations:

- **Workflows API** (`workflows.py`) - Workflow CRUD and execution
- **Agents API** (`agents.py`) - Agent management
- **Tools API** (`tools.py`) - Tool registration and execution
- **Memory API** (`memory.py`) - Memory storage and retrieval
- **Approvals API** (`approvals.py`) - Approval workflow management
- **Auth API** (`auth.py`) - Authentication and authorization
- **Metrics API** (`metrics.py`) - Performance metrics
- **Ops API** (`ops.py`) - Operational endpoints

### 2. LLM Router

**Location**: `backend/app/core/llm.py`

Manages multiple LLM providers with intelligent routing:

- Provider abstraction (OpenAI, Anthropic, etc.)
- Model selection based on task requirements
- Fallback strategies
- Token counting and cost estimation
- Rate limiting and quota management

### 3. Memory System

**Location**: `backend/app/core/memory_*.py`

Dual-layer memory architecture:

**Structured Memory (PostgreSQL)**
- Persistent storage of facts and relationships
- Graph-based knowledge representation
- Transaction support
- Complex queries

**Vector Memory (Qdrant)**
- Semantic embeddings for similarity search
- Fast retrieval of relevant context
- Approximate nearest neighbor search
- Scalable to millions of vectors

### 4. Workflow Engine

**Location**: `backend/app/core/execution_planner.py`

Orchestrates multi-step task execution:

- Workflow definition and validation
- Step execution and state management
- Error handling and retry logic
- Conditional branching
- Parallel execution support

### 5. Browser Automation

**Location**: `backend/app/services/browser/`

Web interaction capabilities:

- Session management
- Screenshot and DOM capture
- Form filling and navigation
- Cookie and storage handling
- JavaScript execution

### 6. Observability System

**Location**: `backend/app/services/observability/`

Comprehensive tracing and monitoring:

- Request correlation
- Trace visualization (Langfuse)
- Performance metrics
- Error tracking
- Audit logging

### 7. Approval System

**Location**: `backend/app/core/approvals.py`

Human-in-the-loop approval workflows:

- Configurable approval policies
- Multi-level approval chains
- Audit trail
- Notification system

### 8. Policy Engine

**Location**: `backend/app/core/policy.py`

Behavior constraints and access control:

- Resource access policies
- Rate limiting
- Behavior constraints
- Policy versioning

## Data Flow

### Workflow Execution Flow

```
1. User submits workflow
   ↓
2. API validates workflow definition
   ↓
3. Workflow engine creates execution plan
   ↓
4. For each step:
   a. Retrieve context from memory
   b. Route to appropriate LLM
   c. Execute LLM call
   d. Store results in memory
   e. Check approval requirements
   f. Execute approved actions
   ↓
5. Collect metrics and traces
   ↓
6. Return results to user
```

### Memory Retrieval Flow

```
1. Agent needs context
   ↓
2. Query memory system
   ↓
3. Structured query (PostgreSQL)
   + Semantic search (Qdrant)
   ↓
4. Combine and rank results
   ↓
5. Return relevant context
```

## Database Schema

### Key Tables

**workflows**
- id, name, description
- definition (JSON)
- created_at, updated_at

**workflow_runs**
- id, workflow_id
- status, result
- started_at, completed_at

**memory**
- id, content, embedding
- metadata (JSON)
- created_at

**approvals**
- id, workflow_run_id
- status, approver_id
- created_at, approved_at

**audit_logs**
- id, action, actor_id
- resource_type, resource_id
- timestamp

## Deployment Architecture

### Single Server Deployment

```
┌─────────────────────────────────┐
│      Docker Container           │
│  ┌─────────────────────────┐   │
│  │  FastAPI Application    │   │
│  │  Workflow Worker        │   │
│  └─────────────────────────┘   │
└─────────────────────────────────┘
         ↓              ↓
    PostgreSQL      Qdrant
```

### Kubernetes Deployment

```
┌──────────────────────────────────────┐
│         Kubernetes Cluster           │
│  ┌────────────────────────────────┐ │
│  │  API Pods (replicas: 3)        │ │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │  Worker Pods (replicas: 2)     │ │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │  PostgreSQL StatefulSet        │ │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │  Qdrant StatefulSet            │ │
│  └────────────────────────────────┘ │
└──────────────────────────────────────┘
```

## Security Architecture

### Authentication & Authorization

- API key authentication
- JWT token support
- Role-based access control (RBAC)
- Tenant isolation

### Data Security

- Encrypted credentials storage
- Input validation and sanitization
- SQL injection prevention
- CORS configuration

### Audit & Compliance

- Comprehensive audit logging
- Request tracing
- User action tracking
- Compliance reporting

## Performance Considerations

### Caching Strategy

- Query result caching (Redis)
- Embedding cache
- LLM response caching
- Database query optimization

### Scalability

- Horizontal scaling of API servers
- Database connection pooling
- Vector database sharding
- Async task processing

### Monitoring

- Request latency tracking
- Error rate monitoring
- Resource utilization metrics
- Custom business metrics

## Extension Points

### Custom Tools

Implement the `Tool` interface to add custom capabilities:

```python
class CustomTool(Tool):
    def execute(self, **kwargs):
        # Implementation
        pass
```

### Custom LLM Providers

Extend `LLMProvider` for new LLM backends:

```python
class CustomLLMProvider(LLMProvider):
    def call(self, prompt, **kwargs):
        # Implementation
        pass
```

### Custom Memory Backends

Implement alternative memory storage:

```python
class CustomMemory(Memory):
    def store(self, content, embedding):
        # Implementation
        pass
```

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | FastAPI | 0.115+ |
| Database | PostgreSQL | 14+ |
| Vector DB | Qdrant | 1.11+ |
| LLM | OpenAI/Anthropic | Latest |
| Browser | Playwright | 1.48+ |
| Tracing | Langfuse | 2.60+ |
| Async | asyncpg | 0.29+ |
| Validation | Pydantic | 2.7+ |
| Server | Uvicorn | 0.30+ |

## Development Workflow

```
Feature Branch
    ↓
Local Testing
    ↓
Code Review (PR)
    ↓
CI/CD Pipeline
    ↓
Integration Tests
    ↓
Merge to develop
    ↓
Release to main
```

---

For more details, see [API Documentation](../../developer/api/API.md) and [Development Guide](./DEVELOPMENT.md).
