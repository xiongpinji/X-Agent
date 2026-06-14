"""X-Agent Python Integration Example

This example demonstrates how to integrate with X-Agent using the Python SDK.

Installation:
    pip install xagent-sdk

Basic usage:
    from xagent_sdk import XAgent, TaskRequest
    
    # Initialize client
    agent = XAgent(base_url="http://localhost:8000", api_key="sk_your_key_here")
    
    # Submit a task
    result = agent.submit_task("Analyze the code quality of my repository")
    
    # Wait for completion
    final_result = result.wait()
    print(f"Status: {final_result.status}")
    print(f"Result: {final_result.output}")
"""

from xagent_sdk import XAgent, TaskRequest, TaskStatus
import time
from typing import Optional


def example_basic_task():
    """Example: Submit a basic task and wait for completion."""
    
    # Initialize the client
    agent = XAgent(
        base_url="http://localhost:8000",
        api_key="sk_your_api_key_here",
    )
    
    # Create a task request
    task = TaskRequest(
        prompt="Analyze this Python code for security issues",
        context={
            "language": "python",
            "code_snippet": """
def authenticate(username, password):
    query = f"SELECT * FROM users WHERE username='{username}'"
    # SQL injection vulnerability!
    return db.execute(query)
"""
        }
    )
    
    # Submit task
    print("Submitting task...")
    run = agent.submit_task(task)
    print(f"Task ID: {run.id}")
    
    # Wait for completion (with timeout)
    print("Waiting for task completion...")
    result = run.wait(timeout=300)
    
    print(f"\nTask Status: {result.status}")
    print(f"Output:\n{result.output}")
    
    if result.status == TaskStatus.COMPLETED:
        print(f"\n✓ Task completed successfully")
        print(f"Metrics: {result.metrics}")
    else:
        print(f"\n✗ Task failed: {result.error}")


def example_polling_task():
    """Example: Submit a task and poll for status."""
    
    agent = XAgent(
        base_url="http://localhost:8000",
        api_key="sk_your_api_key_here",
    )
    
    # Submit task
    task_prompt = "Generate a comprehensive API documentation from the codebase"
    run = agent.submit_task(task_prompt)
    print(f"Task submitted: {run.id}")
    
    # Poll for status
    while True:
        status = run.status()
        print(f"Status: {status.status} - Progress: {status.progress}%")
        
        if status.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            break
        
        time.sleep(5)  # Poll every 5 seconds
    
    # Get final result
    result = run.result()
    print(f"\nFinal result:\n{result}")


def example_streaming_task():
    """Example: Stream task output in real-time."""
    
    agent = XAgent(
        base_url="http://localhost:8000",
        api_key="sk_your_api_key_here",
    )
    
    # Submit task with streaming
    task_prompt = "Refactor my legacy module to use modern Python patterns"
    
    print("Task output:")
    print("-" * 50)
    
    # Stream updates as they arrive
    for update in agent.submit_task_stream(task_prompt):
        if update.event == "output":
            print(update.data, end="", flush=True)
        elif update.event == "status":
            print(f"\n[{update.data}]")
        elif update.event == "error":
            print(f"\n❌ Error: {update.data}")
            break
        elif update.event == "complete":
            print(f"\n✓ Complete: {update.data}")
            break
    
    print("-" * 50)


def example_batch_tasks():
    """Example: Submit multiple tasks and track them."""
    
    agent = XAgent(
        base_url="http://localhost:8000",
        api_key="sk_your_api_key_here",
    )
    
    tasks = [
        "Analyze security vulnerabilities",
        "Check code style and formatting",
        "Generate unit tests",
        "Create API documentation",
    ]
    
    # Submit all tasks
    runs = []
    for prompt in tasks:
        run = agent.submit_task(prompt)
        runs.append(run)
        print(f"Submitted: {prompt} (ID: {run.id})")
    
    # Wait for all to complete
    print("\nWaiting for all tasks...")
    results = agent.wait_for_all(runs, timeout=600)
    
    # Process results
    for prompt, result in zip(tasks, results):
        status = "✓" if result.status == TaskStatus.COMPLETED else "✗"
        print(f"{status} {prompt}: {result.status}")


def example_with_tools():
    """Example: Task with specific tools enabled."""
    
    agent = XAgent(
        base_url="http://localhost:8000",
        api_key="sk_your_api_key_here",
    )
    
    task = TaskRequest(
        prompt="Clone the repository and analyze it",
        tools=["git", "code_analyzer", "file_reader"],  # Use specific tools
        context={
            "repo_url": "https://github.com/example/repo",
        }
    )
    
    run = agent.submit_task(task)
    result = run.wait()
    
    print(f"Result: {result.output}")
    print(f"Tools used: {result.tools_used}")


def example_error_handling():
    """Example: Handle errors and retries gracefully."""
    
    agent = XAgent(
        base_url="http://localhost:8000",
        api_key="sk_your_api_key_here",
        timeout=30,
        max_retries=3,
    )
    
    try:
        task = TaskRequest(
            prompt="Analyze the codebase",
            timeout=60,  # Task timeout
        )
        
        run = agent.submit_task(task)
        result = run.wait()
        
        if result.status == TaskStatus.FAILED:
            print(f"Task failed: {result.error}")
            print(f"Error code: {result.error_code}")
            
            # Optionally retry
            if "timeout" in result.error_code:
                print("Retrying with longer timeout...")
                retry_run = agent.submit_task(
                    task,
                    timeout=120
                )
                result = retry_run.wait()
        
        print(f"Final status: {result.status}")
        
    except Exception as e:
        print(f"Error: {e}")


def example_get_run_history():
    """Example: Retrieve task history."""
    
    agent = XAgent(
        base_url="http://localhost:8000",
        api_key="sk_your_api_key_here",
    )
    
    # Get recent runs
    runs = agent.get_runs(limit=10, status=TaskStatus.COMPLETED)
    
    print("Recent completed tasks:")
    for run in runs:
        print(f"- {run.id}: {run.name} ({run.created_at})")
    
    # Get details of specific run
    if runs:
        first_run = runs[0]
        details = agent.get_run(first_run.id)
        print(f"\nDetails of {first_run.id}:")
        print(f"  Status: {details.status}")
        print(f"  Output: {details.output[:200]}...")


if __name__ == "__main__":
    import sys
    
    examples = {
        "basic": example_basic_task,
        "polling": example_polling_task,
        "streaming": example_streaming_task,
        "batch": example_batch_tasks,
        "tools": example_with_tools,
        "errors": example_error_handling,
        "history": example_get_run_history,
    }
    
    if len(sys.argv) > 1 and sys.argv[1] in examples:
        example_func = examples[sys.argv[1]]
        print(f"\nRunning: {example_func.__name__}\n")
        example_func()
    else:
        print("X-Agent Python Integration Examples")
        print("=" * 50)
        print("\nUsage: python basic.py <example>")
        print("\nAvailable examples:")
        for name, func in examples.items():
            print(f"  {name:15} - {func.__doc__.split(chr(10))[0]}")
        print("\nExample:")
        print("  python basic.py basic")
