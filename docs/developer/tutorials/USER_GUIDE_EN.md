# X-Agent Core User Guide

Welcome to X-Agent Core, an enterprise-grade autonomous agent framework. This guide will help you quickly understand the core features and how to use them.

## Table of Contents

1. [Product Overview](#product-overview)
2. [Core Concepts](#core-concepts)
3. [Key Features](#key-features)
4. [Use Cases](#use-cases)
5. [Quick Navigation](#quick-navigation)

## Product Overview

X-Agent Core is a complete AI agent execution framework that provides:

- **Intelligent Agent Engine**: Multi-turn conversations, task planning, automatic execution, and failure recovery
- **Workflow Orchestration**: DAG-based workflow engine supporting complex multi-step task orchestration
- **Advanced Memory System**: Graph-based memory storage with semantic search and context retrieval
- **Browser Automation**: Integrated Playwright support for web interaction and data extraction
- **Desktop Automation**: Desktop UI operations, input method control, clipboard management
- **Observability**: Complete request tracing, audit logging, and performance monitoring
- **Enterprise Features**: Multi-tenant support, RBAC access control, approval workflows

## Core Concepts

### Agent

An Agent is the core execution unit in X-Agent. Each Agent can:

- Understand natural language tasks
- Create execution plans
- Call tools and services
- Recover from failures
- Learn and improve

**Example**: A data analysis Agent can understand "analyze last month's sales data" and automatically break it down into data retrieval, cleaning, analysis, and visualization steps.

### Workflow

A Workflow is a series of ordered task nodes supporting:

- **Sequential Execution**: Nodes execute in order
- **Conditional Branching**: Choose different execution paths based on conditions
- **Parallel Execution**: Multiple nodes execute simultaneously
- **Error Handling**: Automatic retry or compensation on failure

**Example**: An order processing workflow might include: validate order → check inventory → generate shipping label → update inventory → send notification.

### Memory

The Memory System provides:

- **Persistent Storage**: Graph-based memory with semantic indexing
- **Context Retrieval**: Automatic context retrieval for task execution
- **Learning**: Agents learn from past experiences
- **Semantic Search**: Find relevant information using natural language

### Tools

Tools are the actions Agents can perform:

- **Browser Automation**: Web interaction and data extraction
- **Desktop Automation**: UI operations and system interactions
- **API Calls**: Integration with external services
- **Data Processing**: Data transformation and analysis
- **File Operations**: File system operations

## Key Features

### 1. Multi-LLM Router

Seamlessly switch between different LLM providers:

```python
from x_agent import Agent

agent = Agent(
    llm_provider="auto",  # Automatically select best provider
    model="gpt-4"
)
```

### 2. Workflow Orchestration

Define complex workflows with conditional logic:

```python
from x_agent import Workflow, Task

workflow = Workflow(
    name="data_pipeline",
    tasks=[
        Task(name="fetch_data", action="api_call"),
        Task(name="process_data", action="transform"),
        Task(name="save_results", action="store")
    ]
)
```

### 3. Memory Management

Leverage the advanced memory system:

```python
from x_agent import Agent

agent = Agent()
agent.memory.store("key_insight", "important_data")
context = agent.memory.retrieve("relevant_context")
```

### 4. Browser Automation

Automate web interactions:

```python
from x_agent import BrowserAgent

browser = BrowserAgent()
browser.navigate("https://example.com")
browser.click("button.submit")
data = browser.extract_data("table.results")
```

### 5. Approval Workflows

Implement human-in-the-loop approval:

```python
from x_agent import ApprovalWorkflow

approval = ApprovalWorkflow(
    action="delete_data",
    approvers=["admin@example.com"],
    timeout=3600
)
```

## Use Cases

### 1. Data Analysis & Reporting

Automate data collection, analysis, and report generation:

- Fetch data from multiple sources
- Clean and transform data
- Generate insights and visualizations
- Create and distribute reports

### 2. Customer Support Automation

Automate support ticket handling:

- Classify incoming tickets
- Route to appropriate teams
- Generate responses using knowledge base
- Escalate complex issues to humans

### 3. Business Process Automation

Automate repetitive business processes:

- Order processing and fulfillment
- Invoice generation and payment tracking
- Employee onboarding workflows
- Compliance and audit processes

### 4. Web Scraping & Data Extraction

Extract data from websites:

- Monitor competitor pricing
- Collect market research data
- Extract structured data from unstructured sources
- Automate data entry tasks

### 5. Integration & API Orchestration

Orchestrate complex API workflows:

- Multi-step API chains
- Data transformation between systems
- Event-driven automation
- Real-time data synchronization

## Quick Navigation

### For New Users

1. Start with [Quick Start](../../operations/setup/QUICKSTART_DOCS.md) - 5-minute setup
2. Read [Agent Basics](./tutorials/01-agent-basics.md) - Core concepts
3. Try [Workflow Orchestration](./tutorials/02-workflow-orchestration.md) - Build your first workflow

### For Developers

1. Review [Architecture Guide](../../concepts/architecture/ARCHITECTURE.md) - System design
2. Check [API Reference](../api/API.md) - API endpoints
3. Read [Contributing Guide](../CONTRIBUTING.md) - How to contribute

### For DevOps/Operations

1. See [Installation Guide](../../operations/setup/INSTALL.md) - Setup instructions
2. Review [Deployment Guide](../../operations/deployment/DEPLOYMENT_DETAILED.md) - Production deployment
3. Check [Operations Guide](../../operations/OPERATIONS.md) - Monitoring and maintenance

### For Troubleshooting

1. Check [FAQ](../../operations/support/FAQ.md) - Common questions
2. Review [Troubleshooting Guide](../../operations/support/TROUBLESHOOTING.md) - Common issues
3. See [Common Issues](../../operations/support/troubleshooting/COMMON_ISSUES.md) - Detailed solutions

## Getting Help

- **Documentation**: Check [docs/README.md](./README.md)
- **FAQ**: See [FAQ.md](../../operations/support/FAQ.md)
- **Issues**: Report bugs on GitHub
- **Community**: Join our community discussions

## Next Steps

- [Installation Guide](../../operations/setup/INSTALL.md) - Get started with installation
- [Quick Start](../../operations/setup/QUICKSTART_DOCS.md) - 5-minute setup guide
- [Tutorials](./tutorials/GETTING_STARTED.md) - Step-by-step tutorials
- [Examples](./examples/README.md) - Code examples

---

Last Updated: 2026-05-27
