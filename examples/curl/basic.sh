#!/bin/bash
# X-Agent cURL Integration Examples
# 
# These examples demonstrate how to interact with X-Agent API using curl.
#
# Prerequisites:
#   - X-Agent running on http://localhost:8000
#   - curl installed
#   - jq for JSON parsing (optional but recommended)
#
# Configuration:
export XAGENT_BASE_URL="${XAGENT_BASE_URL:-http://localhost:8000}"
export XAGENT_API_KEY="${XAGENT_API_KEY:-sk_your_api_key_here}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color


# ==============================================================================
# Example 1: Basic task submission
# ==============================================================================
example_basic_task() {
    echo -e "${YELLOW}Example 1: Basic Task Submission${NC}"
    
    # Submit a task
    echo "Submitting task..."
    response=$(curl -s -X POST "$XAGENT_BASE_URL/api/v1/agent/run" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $XAGENT_API_KEY" \
        -d '{
            "prompt": "Analyze this Python code for security vulnerabilities",
            "context": {
                "language": "python",
                "code": "def authenticate(user, pwd):\n    query = f\"SELECT * FROM users WHERE user={user}\"\n    return db.execute(query)"
            }
        }')
    
    # Extract run ID using jq or grep
    if command -v jq &> /dev/null; then
        run_id=$(echo "$response" | jq -r '.run_id')
        status=$(echo "$response" | jq -r '.status')
    else
        run_id=$(echo "$response" | grep -o '"run_id":"[^"]*"' | cut -d'"' -f4)
        status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    fi
    
    echo "Task ID: $run_id"
    echo "Status: $status"
    
    # Wait for completion
    echo "Waiting for task completion..."
    max_attempts=60
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        result=$(curl -s -X GET "$XAGENT_BASE_URL/api/v1/agent/run/$run_id" \
            -H "X-API-Key: $XAGENT_API_KEY")
        
        if command -v jq &> /dev/null; then
            task_status=$(echo "$result" | jq -r '.status')
            output=$(echo "$result" | jq -r '.output // empty')
        else
            task_status=$(echo "$result" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 | head -1)
        fi
        
        echo "Status: $task_status"
        
        if [[ "$task_status" == "completed" || "$task_status" == "failed" ]]; then
            echo "Task completed!"
            if [ ! -z "$output" ]; then
                echo "Output: $output"
            fi
            break
        fi
        
        sleep 5
        ((attempt++))
    done
    
    echo ""
}


# ==============================================================================
# Example 2: Batch submit multiple tasks
# ==============================================================================
example_batch_tasks() {
    echo -e "${YELLOW}Example 2: Batch Submit Multiple Tasks${NC}"
    
    tasks=(
        "Check code style and formatting"
        "Analyze security vulnerabilities"
        "Generate unit test cases"
        "Create API documentation"
    )
    
    declare -a run_ids
    
    # Submit all tasks
    for prompt in "${tasks[@]}"; do
        echo "Submitting: $prompt"
        response=$(curl -s -X POST "$XAGENT_BASE_URL/api/v1/agent/run" \
            -H "Content-Type: application/json" \
            -H "X-API-Key: $XAGENT_API_KEY" \
            -d "{\"prompt\": \"$prompt\"}")
        
        if command -v jq &> /dev/null; then
            run_id=$(echo "$response" | jq -r '.run_id')
        else
            run_id=$(echo "$response" | grep -o '"run_id":"[^"]*"' | cut -d'"' -f4)
        fi
        
        run_ids+=("$run_id")
        echo "  Task ID: $run_id"
    done
    
    # Poll all tasks
    echo "Waiting for all tasks to complete..."
    completed=0
    
    for i in "${!run_ids[@]}"; do
        echo "Checking task ${run_ids[$i]}..."
        
        while true; do
            result=$(curl -s -X GET "$XAGENT_BASE_URL/api/v1/agent/run/${run_ids[$i]}" \
                -H "X-API-Key: $XAGENT_API_KEY")
            
            if command -v jq &> /dev/null; then
                status=$(echo "$result" | jq -r '.status')
            else
                status=$(echo "$result" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 | head -1)
            fi
            
            if [[ "$status" == "completed" || "$status" == "failed" ]]; then
                echo "  ${tasks[$i]}: $status"
                ((completed++))
                break
            fi
            
            sleep 2
        done
    done
    
    echo "All tasks completed: $completed/${#run_ids[@]}"
    echo ""
}


# ==============================================================================
# Example 3: List task history
# ==============================================================================
example_list_history() {
    echo -e "${YELLOW}Example 3: List Task History${NC}"
    
    response=$(curl -s -X GET "$XAGENT_BASE_URL/api/v1/agent/runs?limit=10&status=completed" \
        -H "X-API-Key: $XAGENT_API_KEY")
    
    echo "Recent completed tasks:"
    
    if command -v jq &> /dev/null; then
        echo "$response" | jq '.runs[] | "\(.id): \(.name) (\(.created_at))"'
    else
        echo "$response"
    fi
    
    echo ""
}


# ==============================================================================
# Example 4: Get specific task details
# ==============================================================================
example_get_task_details() {
    echo -e "${YELLOW}Example 4: Get Task Details${NC}"
    
    # First, get a task ID
    run_id="$1"
    
    if [ -z "$run_id" ]; then
        echo "Usage: example_get_task_details <run_id>"
        return 1
    fi
    
    echo "Fetching details for task: $run_id"
    
    response=$(curl -s -X GET "$XAGENT_BASE_URL/api/v1/agent/run/$run_id" \
        -H "X-API-Key: $XAGENT_API_KEY")
    
    if command -v jq &> /dev/null; then
        echo "$response" | jq '.'
    else
        echo "$response"
    fi
    
    echo ""
}


# ==============================================================================
# Example 5: Create and manage API keys
# ==============================================================================
example_manage_api_keys() {
    echo -e "${YELLOW}Example 5: Manage API Keys${NC}"
    
    # Create new API key
    echo "Creating new API key..."
    key_response=$(curl -s -X POST "$XAGENT_BASE_URL/api/v1/api-keys" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $XAGENT_API_KEY" \
        -d '{
            "name": "Integration test key",
            "expires_in_days": 30
        }')
    
    if command -v jq &> /dev/null; then
        new_key=$(echo "$key_response" | jq -r '.key')
        key_id=$(echo "$key_response" | jq -r '.id')
    else
        new_key=$(echo "$key_response" | grep -o '"key":"[^"]*"' | cut -d'"' -f4)
        key_id=$(echo "$key_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    fi
    
    echo "Created API key: $key_id"
    echo "Key: $new_key"
    
    # List all API keys
    echo -e "\nListing all API keys..."
    keys_response=$(curl -s -X GET "$XAGENT_BASE_URL/api/v1/api-keys" \
        -H "X-API-Key: $XAGENT_API_KEY")
    
    if command -v jq &> /dev/null; then
        echo "$keys_response" | jq '.keys[] | {id, name, created_at, last_used_at}'
    else
        echo "$keys_response"
    fi
    
    echo ""
}


# ==============================================================================
# Example 6: Webhook management
# ==============================================================================
example_webhooks() {
    echo -e "${YELLOW}Example 6: Webhook Management${NC}"
    
    # Create webhook
    echo "Creating webhook..."
    webhook_response=$(curl -s -X POST "$XAGENT_BASE_URL/api/v1/webhooks" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $XAGENT_API_KEY" \
        -d '{
            "name": "GitHub Push Webhook",
            "url": "https://example.com/webhook",
            "events": ["github.push", "github.pull_request"],
            "secret": "your_secret_key_here"
        }')
    
    if command -v jq &> /dev/null; then
        webhook_id=$(echo "$webhook_response" | jq -r '.id')
    else
        webhook_id=$(echo "$webhook_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    fi
    
    echo "Created webhook: $webhook_id"
    
    # List webhooks
    echo -e "\nListing all webhooks..."
    list_response=$(curl -s -X GET "$XAGENT_BASE_URL/api/v1/webhooks?limit=5" \
        -H "X-API-Key: $XAGENT_API_KEY")
    
    if command -v jq &> /dev/null; then
        echo "$list_response" | jq '.[] | {id, name, url, active}'
    else
        echo "$list_response"
    fi
    
    # Test webhook
    echo -e "\nTesting webhook..."
    test_response=$(curl -s -X POST "$XAGENT_BASE_URL/api/v1/webhooks/$webhook_id/test" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $XAGENT_API_KEY" \
        -d '{"event_type": "github.push"}')
    
    echo "$test_response"
    echo ""
}


# ==============================================================================
# Example 7: Get system health and metrics
# ==============================================================================
example_system_health() {
    echo -e "${YELLOW}Example 7: System Health and Metrics${NC}"
    
    # Health check
    echo "Checking system health..."
    health_response=$(curl -s -X GET "$XAGENT_BASE_URL/health")
    
    if command -v jq &> /dev/null; then
        echo "$health_response" | jq '.'
    else
        echo "$health_response"
    fi
    
    # Get metrics
    echo -e "\nFetching metrics..."
    metrics_response=$(curl -s -X GET "$XAGENT_BASE_URL/metrics" \
        -H "X-API-Key: $XAGENT_API_KEY")
    
    echo "$metrics_response" | head -20
    echo "..."
    echo ""
}


# ==============================================================================
# Example 8: Stream task output
# ==============================================================================
example_stream_task() {
    echo -e "${YELLOW}Example 8: Stream Task Output${NC}"
    
    echo "Submitting streaming task..."
    
    # Note: Streaming requires WebSocket or Server-Sent Events
    # This example uses curl with --raw output
    curl -s -X POST "$XAGENT_BASE_URL/api/v1/agent/run/stream" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $XAGENT_API_KEY" \
        -d '{
            "prompt": "Generate documentation",
            "stream": true
        }' | while IFS= read -r line; do
            echo "Stream: $line"
        done
    
    echo ""
}


# ==============================================================================
# Helper functions
# ==============================================================================

print_usage() {
    cat << EOF
X-Agent cURL Integration Examples

Usage: $0 <example> [options]

Examples:
    basic       - Basic task submission and polling
    batch       - Batch submit multiple tasks
    history     - List task history
    details     - Get specific task details (requires task_id)
    keys        - Create and manage API keys
    webhooks    - Create and manage webhooks
    health      - Check system health and metrics
    stream      - Stream task output in real-time
    all         - Run all examples

Environment variables:
    XAGENT_BASE_URL   - X-Agent API URL (default: http://localhost:8000)
    XAGENT_API_KEY    - API Key for authentication

Examples:
    # Run basic example
    $0 basic
    
    # Run with custom server
    XAGENT_BASE_URL=http://api.example.com $0 batch
    
    # Get task details
    $0 details abc123def456

EOF
}


# ==============================================================================
# Main
# ==============================================================================

if [ $# -eq 0 ]; then
    print_usage
    exit 1
fi

case "$1" in
    basic)
        example_basic_task
        ;;
    batch)
        example_batch_tasks
        ;;
    history)
        example_list_history
        ;;
    details)
        example_get_task_details "$2"
        ;;
    keys)
        example_manage_api_keys
        ;;
    webhooks)
        example_webhooks
        ;;
    health)
        example_system_health
        ;;
    stream)
        example_stream_task
        ;;
    all)
        example_basic_task
        example_batch_tasks
        example_list_history
        example_manage_api_keys
        example_webhooks
        example_system_health
        ;;
    *)
        echo "Unknown example: $1"
        print_usage
        exit 1
        ;;
esac
