# X-Agent CLI Guide

## Overview

The **X-Agent CLI** (`xagent`) is a command-line interface for the X-Agent intelligent agent framework. It provides enterprise-grade capabilities for managing agents, tools, and workflows with support for both remote HTTP-based API calls and local direct module imports.

### Dual Mode Architecture

X-Agent CLI supports two execution modes:

- **HTTP Mode** (default): Connects to a remote X-Agent backend API for distributed execution
- **Local Mode**: Uses direct Python imports for testing and local development

## Installation

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Install from Source

From the project root directory:

```bash
pip install -e ".[cli]"
```

This installs X-Agent core with CLI dependencies including:
- `typer` — CLI framework
- `rich` — terminal formatting
- `prompt-toolkit` — interactive REPL
- `pyyaml` — YAML workflow file support

### Verify Installation

```bash
xagent --version
```

Expected output:
```
xagent version 0.1.0
```

## Configuration

### Configuration Hierarchy

Configuration is loaded in this priority order (highest to lowest):

1. **Command-line flags** — `--api-url`, `--api-key`, `--mode`, `--output`
2. **Environment variables** — `XAGENT_API_BASE_URL`, `XAGENT_API_KEY`, `XAGENT_MODE`, `XAGENT_OUTPUT_FORMAT`, `XAGENT_TIMEOUT`
3. **Configuration file** — `~/.xagent/config.toml`
4. **Default values**

### Configuration File Location

`~/.xagent/config.toml`

### Configuration Properties

| Property | Env Variable | Type | Default | Description |
|----------|-------------|------|---------|-------------|
| `api_base_url` | `XAGENT_API_BASE_URL` | string | `http://localhost:8000` | X-Agent API endpoint URL |
| `api_key` | `XAGENT_API_KEY` | string | (none) | API authentication key (optional) |
| `mode` | `XAGENT_MODE` | `http` or `local` | `http` | Execution mode |
| `timeout` | `XAGENT_TIMEOUT` | integer | `30` | Request timeout in seconds |
| `output_format` | `XAGENT_OUTPUT_FORMAT` | `rich`, `json`, or `plain` | `rich` | Output formatting style |

### Example Configuration File

```toml
[xagent]
api_base_url = "http://api.example.com"
mode = "http"
timeout = 30
output_format = "rich"
api_key = "your-api-key-here"
```

### Initialize Configuration

Use `xagent init setup` to create or update configuration interactively:

```bash
# Interactive setup (prompts for all values)
xagent init setup

# Non-interactive setup with options
xagent init setup --api-url http://example.com --mode http --api-key mykey
```

Example output:
```
X-Agent CLI Configuration Setup
==================================================
Configuration file already exists: /home/user/.xagent/config.toml

Enter configuration values (press Enter for defaults):
API Base URL [http://localhost:8000]: http://api.example.com
Client Mode (http/local) [http]: http
API Key (optional) []: myapikey123

Configuration saved to /home/user/.xagent/config.toml

Active Configuration:
  API URL: http://api.example.com
  Mode: http
  Timeout: 30s
  Output Format: rich
  API Key: ****...3
```

### View Current Configuration

```bash
xagent config-show
```

Example output:
```
Current CLI Configuration:
  API URL: http://localhost:8000
  Mode: http
  Timeout: 30s
  Output Format: rich
  API Key: (not set)
```

## Global Options

These options work with any command and can be placed before or after the command name:

```bash
xagent [OPTIONS] COMMAND [ARGS]
```

| Option | Environment Variable | Description |
|--------|---------------------|-------------|
| `--api-url` TEXT | `XAGENT_API_BASE_URL` | Override API base URL |
| `--api-key` TEXT | `XAGENT_API_KEY` | Override API key |
| `--mode` TEXT | `XAGENT_MODE` | Override mode (http/local) |
| `--output` TEXT | `XAGENT_OUTPUT_FORMAT` | Override output format (rich/json/plain) |
| `--version` | — | Show version and exit |
| `--help` | — | Show help message and exit |

### Examples of Global Options

```bash
# Use HTTP mode with custom API URL
xagent --api-url http://api.example.com agent list

# Output as JSON
xagent --output json agent list

# Use local mode
xagent --mode local health

# Override API key for single command
xagent --api-key secret123 health
```

## Command Reference

### `xagent health`

Check X-Agent backend health and connectivity.

**Usage:**
```bash
xagent health
```

**Output:**
- Success: `Backend is healthy (mode: http)`
- Failure: Error message with exit code 1

**Examples:**
```bash
# Check HTTP backend
xagent health

# Check with custom endpoint
xagent --api-url http://api.example.com health

# Check local mode
xagent --mode local health
```

### `xagent agent` — Agent Management

#### `xagent agent run`

Run an agent with a task description.

**Syntax:**
```bash
xagent agent run TASK [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `TASK` | Yes | Task description for the agent to execute |

**Options:**
| Option | Type | Description |
|--------|------|-------------|
| `--scope` TEXT | Multiple | Permission scopes (repeatable); default: `tools:read`, `memory:read`, `memory:write` |
| `--context` TEXT | String | Extra context as JSON string |
| `--stream/--no-stream` | Flag | Stream results as they arrive (default: off) |

**Examples:**
```bash
# Simple task
xagent agent run "Analyze market trends"

# With permission scopes
xagent agent run "Search for info" --scope tools:read --scope memory:read

# With JSON context
xagent agent run "Process data" --context '{"format":"json","source":"api"}'

# With streaming output
xagent agent run "Long task" --stream

# Multiple scopes and context
xagent agent run "Complex task" --scope tools:full --scope memory:full --context '{"mode":"strict"}'
```

**Output (JSON format):**
```json
{
  "trace_id": "abc123xyz789",
  "status": "completed",
  "task": "Analyze market trends",
  "tool_calls": 5
}
```

#### `xagent agent list`

List all available agents in the system.

**Syntax:**
```bash
xagent agent list
```

**Output:**
Formatted table with columns: ID, Name, Status, Capabilities

**Examples:**
```bash
# List agents with default formatting
xagent agent list

# List agents as JSON
xagent --output json agent list

# List agents with custom API endpoint
xagent --api-url http://api.example.com agent list
```

### `xagent tools` — Tool Management

#### `xagent tools list`

List all available tools registered in the X-Agent system.

**Syntax:**
```bash
xagent tools list
```

**Output:**
Formatted table with columns: Name, Description, Category, Status

**Examples:**
```bash
# List all tools
xagent tools list

# List tools with JSON output
xagent --output json tools list

# List tools from local mode
xagent --mode local tools list
```

### `xagent workflow` — Workflow Management

#### `xagent workflow list`

List all workflows available in the system.

**Syntax:**
```bash
xagent workflow list
```

**Output:**
Formatted table with columns: ID, Name, Nodes, Edges, Status

**Examples:**
```bash
xagent workflow list
xagent --output json workflow list
```

#### `xagent workflow create`

Create a new workflow from specification.

**Syntax:**
```bash
xagent workflow create [OPTIONS]
```

**Options:**
| Option | Type | Description |
|--------|------|-------------|
| `--file` TEXT | Path | Path to workflow spec file (JSON or YAML) |
| `--spec` TEXT | String | Workflow spec as JSON string |

**File Format Support:**
- `.json` — JSON workflow specification
- `.yaml` / `.yml` — YAML workflow specification (requires PyYAML)

**Workflow Spec Structure:**
```json
{
  "name": "workflow-name",
  "description": "optional description",
  "nodes": [],
  "edges": []
}
```

**Examples:**
```bash
# Create from file
xagent workflow create --file workflow.json

# Create from YAML file
xagent workflow create --file workflow.yaml

# Create from JSON string
xagent workflow create --spec '{"name":"my-workflow","nodes":[],"edges":[]}'
```

**Output:**
```json
{
  "workflow_id": "wf_abc123",
  "name": "my-workflow",
  "status": "created"
}
```

#### `xagent workflow run`

Execute a workflow with optional inputs.

**Syntax:**
```bash
xagent workflow run WORKFLOW_ID [OPTIONS]
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `WORKFLOW_ID` | Yes | ID of the workflow to execute |

**Options:**
| Option | Type | Description |
|--------|------|-------------|
| `--inputs` TEXT | String | Workflow inputs as JSON string |

**Examples:**
```bash
# Run workflow without inputs
xagent workflow run my-workflow-id

# Run with JSON inputs
xagent workflow run my-workflow-id --inputs '{"param1":"value1","param2":42}'
```

**Output:**
```json
{
  "run_id": "run_xyz789",
  "workflow_id": "my-workflow-id",
  "status": "running"
}
```

#### `xagent workflow status`

Get the current status of a workflow.

**Syntax:**
```bash
xagent workflow status WORKFLOW_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `WORKFLOW_ID` | Yes | ID of the workflow to check |

**Output:**
```json
{
  "workflow_id": "my-workflow-id",
  "status": "completed",
  "run_count": 3,
  "latest_run_id": "run_xyz789"
}
```

**Examples:**
```bash
xagent workflow status my-workflow-id
xagent --output json workflow status my-workflow-id
```

### `xagent init` — Project Initialization

#### `xagent init setup`

Initialize or update CLI configuration interactively.

**Syntax:**
```bash
xagent init setup [OPTIONS]
```

**Options:**
| Option | Type | Description |
|--------|------|-------------|
| `--api-url` TEXT | URL | API base URL (overrides prompt) |
| `--api-key` TEXT | String | API key (overrides prompt) |
| `--mode` TEXT | Enum | Client mode: http or local (overrides prompt) |
| `--interactive/--no-interactive` | Flag | Use interactive mode (default: true if no options provided) |

**Examples:**
```bash
# Interactive setup
xagent init setup

# Non-interactive setup
xagent init setup --api-url http://localhost:8000 --mode http

# With API key
xagent init setup --api-url http://api.example.com --api-key secret123
```

**Output:**
```
X-Agent CLI Configuration Setup
==================================================
Configuration file already exists: /home/user/.xagent/config.toml

Configuration saved to /home/user/.xagent/config.toml

Active Configuration:
  API URL: http://localhost:8000
  Mode: http
  Timeout: 30s
  Output Format: rich
  API Key: (not set)
```

#### `xagent init project`

Initialize a new X-Agent project structure with directories and config templates.

**Syntax:**
```bash
xagent init project [OPTIONS]
```

**Options:**
| Option | Type | Description |
|--------|------|-------------|
| `--name` TEXT | String | Project name (prompts if not provided) |
| `--path` TEXT | Path | Project directory path (default: current directory) |

**Project Structure Created:**
```
my-project/
├── .xagent/
│   └── config.toml          (project config template)
├── workflows/
│   └── example.json         (example workflow)
├── tools/                   (custom tools directory)
├── data/                    (data files)
└── .gitignore               (git ignore rules)
```

**Examples:**
```bash
# Create project interactively
xagent init project

# Create with name
xagent init project --name my-project

# Create in specific directory
xagent init project --path ./my-project --name my-project
```

**Output:**
```
Creating project: my-project at /home/user/my-project
  Created directory: .xagent
  Created directory: workflows
  Created directory: tools
  Created directory: data
  Created configuration: .xagent/config.toml
  Created example workflow: workflows/example.json
  Created .gitignore

Project 'my-project' initialized successfully!

Next steps:
  1. cd my-project
  2. xagent init setup
  3. xagent agent run 'Your task here'
```

### `xagent repl` — Interactive Mode

Start an interactive REPL (Read-Eval-Print Loop) for X-Agent operations.

**Syntax:**
```bash
xagent repl
```

**Features:**
- Command history (stored in `~/.xagent/repl_history`)
- Auto-completion for built-in commands
- Multi-line command support
- Direct access to agents, tools, and workflows

**Built-in Commands:**
| Command | Description |
|---------|-------------|
| `help` | Show available commands |
| `run <task>` | Run an agent task |
| `agents` | List all agents |
| `agent` | Agent commands: `agent list` |
| `tools` | List all available tools |
| `workflows` | List all workflows |
| `status <workflow_id>` | Get workflow status |
| `clear` | Clear screen |
| `exit` / `quit` | Exit REPL |

**Examples:**
```bash
# Start REPL
xagent repl

# Start REPL with custom API endpoint
xagent --api-url http://api.example.com repl

# Start in local mode
xagent --mode local repl
```

**Example REPL Session:**
```
xagent> help
Available commands:
  help                Show available commands
  run <task>          Run an agent task
  agents              List all agents
  tools               List all available tools
  workflows           List all workflows
  status <id>         Get workflow status
  clear               Clear screen
  exit                Exit REPL

xagent> agents
ID     Name           Status      Capabilities
────── ────────────── ─────────── ─────────────────
age1   Research Agent active      search, analyze
age2   Writer Agent   active      write, review

xagent> run Analyze the latest news
Executing: Analyze the latest news
trace_id: abc123
status: completed

xagent> exit
```

## Execution Modes

### HTTP Mode vs Local Mode

| Feature | HTTP Mode | Local Mode |
|---------|-----------|-----------|
| **Architecture** | Remote API calls | Direct Python imports |
| **Use Case** | Production, distributed teams | Development, testing, local |
| **Latency** | Network dependent | Instant |
| **Requires** | Running backend service | Python environment |
| **Scalability** | Horizontal (multiple servers) | Vertical (single machine) |
| **Authentication** | API key required | Not required |
| **Default** | Yes | Optional |

### When to Use HTTP Mode

- Production deployments
- Distributed teams
- Running on remote servers
- Multi-instance setups
- When backend is managed separately

```bash
xagent --mode http agent run "Your task"
xagent --api-url http://api.company.com agent list
```

### When to Use Local Mode

- Local development
- Unit testing
- CI/CD pipelines
- Offline environments
- Prototyping

```bash
xagent --mode local agent run "Your task"
```

## Output Formats

### Rich Format (default)

Human-friendly formatted output with colors and tables.

```bash
xagent agent list
```

Output: Colored table with formatted columns

### JSON Format

Machine-readable JSON output.

```bash
xagent --output json agent list
```

Output: Valid JSON array or object

### Plain Format

Plain text without formatting.

```bash
xagent --output plain agent list
```

Output: Tab-separated or simple text

## Troubleshooting

### Connection Errors

**Issue:** `Failed to connect to API`

**Solutions:**
1. Verify API URL is correct:
   ```bash
   xagent config-show
   ```
2. Check if backend is running:
   ```bash
   xagent health
   ```
3. Override API URL:
   ```bash
   xagent --api-url http://correct-url.com health
   ```

### Authentication Failures

**Issue:** `Authentication failed` or `Invalid API key`

**Solutions:**
1. Verify API key is set:
   ```bash
   xagent config-show
   ```
2. Provide API key via environment variable:
   ```bash
   export XAGENT_API_KEY=your-key
   xagent health
   ```
3. Or via command-line flag:
   ```bash
   xagent --api-key your-key health
   ```

### Invalid JSON in Options

**Issue:** `Invalid JSON in --context` or `Invalid JSON in --spec`

**Solutions:**
1. Ensure JSON is properly formatted:
   ```bash
   # Wrong (missing quotes)
   xagent agent run "task" --context '{key:value}'
   
   # Correct
   xagent agent run "task" --context '{"key":"value"}'
   ```
2. Use jq to validate JSON:
   ```bash
   echo '{"key":"value"}' | jq .
   ```

### Configuration File Issues

**Issue:** `Failed to load configuration`

**Solutions:**
1. Check file exists and is readable:
   ```bash
   cat ~/.xagent/config.toml
   ```
2. Verify TOML syntax is valid:
   ```bash
   xagent config-show
   ```
3. Recreate configuration:
   ```bash
   rm ~/.xagent/config.toml
   xagent init setup
   ```

### REPL Connection Issues

**Issue:** REPL starts but commands fail

**Solutions:**
1. Check backend health before starting REPL:
   ```bash
   xagent health
   ```
2. Try with verbose mode (check logs)
3. Verify correct mode is set:
   ```bash
   xagent --mode http repl
   ```

### Timeout Issues

**Issue:** Requests timing out

**Solutions:**
1. Increase timeout value:
   ```bash
   export XAGENT_TIMEOUT=60
   xagent agent run "long-running-task"
   ```
2. Or set via config file:
   ```toml
   [xagent]
   timeout = 60
   ```

## Environment Variables

Quick reference for environment variables that override configuration:

```bash
# API configuration
export XAGENT_API_BASE_URL=http://api.example.com
export XAGENT_API_KEY=your-secret-key

# Execution mode
export XAGENT_MODE=http  # or 'local'

# Output and timeout
export XAGENT_OUTPUT_FORMAT=json  # or 'rich', 'plain'
export XAGENT_TIMEOUT=30
```

## Common Workflows

### Initialize a New Project

```bash
# Create project structure
xagent init project --name my-agent-project
cd my-agent-project

# Setup configuration
xagent init setup

# Verify setup
xagent health
```

### Run a Simple Agent Task

```bash
xagent agent run "Analyze sales data from Q3"
```

### Create and Run a Workflow

```bash
# Create workflow from JSON
xagent workflow create --spec '{
  "name": "data-pipeline",
  "nodes": [],
  "edges": []
}'

# Run the workflow
xagent workflow run data-pipeline-id

# Check status
xagent workflow status data-pipeline-id
```

### Use Interactive Mode for Development

```bash
# Start REPL
xagent repl

# Inside REPL
xagent> agents
xagent> run Process customer feedback
xagent> workflows
xagent> status workflow-id
xagent> exit
```

## Best Practices

1. **Configuration Management**
   - Use `~/.xagent/config.toml` for persistent settings
   - Use environment variables for CI/CD pipelines
   - Use command-line flags for temporary overrides

2. **Output Formatting**
   - Use `--output json` for scripts and automation
   - Use `--output rich` for interactive terminal use
   - Use `--output plain` for log files

3. **Error Handling**
   - Always check `xagent health` before running complex tasks
   - Use `--mode local` for development/testing
   - Validate JSON input before passing to options

4. **Security**
   - Never commit API keys to version control
   - Use environment variables for sensitive data
   - Rotate API keys regularly
   - Use HTTPS URLs in production

5. **Performance**
   - Use `--stream` flag for long-running tasks
   - Set appropriate timeout values for different task types
   - Run workflows locally first before deploying

## Advanced Usage

### Batch Processing

Run multiple tasks in a loop:

```bash
for task in "Task 1" "Task 2" "Task 3"; do
  xagent agent run "$task" --output json | jq .
done
```

### JSON Processing

Extract specific data:

```bash
xagent --output json agent list | jq '.[] | {id: .ID, name: .Name}'
```

### Piping and Integration

Combine with other CLI tools:

```bash
# Get agent output and pipe to file
xagent agent list > agents.txt

# Chain with grep
xagent --output json agent list | grep -i "research"
```

