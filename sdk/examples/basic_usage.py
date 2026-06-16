"""
Example: Basic Usage of X-Agent SDK

This example demonstrates:
1. Health check
2. Task submission and polling
3. Chat interaction
4. Error handling
"""

from xagent_sdk import XAgent
from xagent_sdk.exceptions import (
    TaskTimeoutError,
    AuthenticationError,
    ServerError,
)


def main():
    # Initialize the client
    client = XAgent(
        base_url="http://localhost:8000",
        api_key="your-api-key",  # Optional
        timeout=30.0,
    )

    try:
        # Check server health
        print("Checking server health...")
        health = client.health()
        print(f"✓ Server status: {health.status}")
        print(f"✓ Version: {health.version}")
        print(f"✓ Components: {health.components}")
        print()

        # Interactive chat
        print("Chatting with agent...")
        response = client.chat(
            "What are the main security considerations for a web API?"
        )
        print(f"Agent: {response.content}")
        print(f"Model: {response.model}")
        print(f"Tokens: {response.usage}")
        print()

        # Submit a task
        print("Submitting analysis task...")
        task = client.submit_task(
            description="Analyze code quality and identify issues",
            repo="https://github.com/example/project",
            branch="main",
            params={"max_issues": 10, "include_security": True},
            timeout_seconds=600,
        )
        print(f"✓ Task submitted: {task.task_id}")
        print()

        # Wait for task completion
        print("Waiting for task completion (this may take a while)...")
        result = task.wait(timeout=600, poll_interval=5)

        print(f"✓ Task completed!")
        print(f"  Status: {result.status}")
        print(f"  Duration: {result.duration_ms}ms")

        if result.pr_url:
            print(f"  PR: {result.pr_url}")

        if result.result:
            print(f"  Result: {result.result}")

        if result.error:
            print(f"  Error: {result.error}")

    except TaskTimeoutError as e:
        print(f"✗ Task timed out: {e}")
    except AuthenticationError as e:
        print(f"✗ Authentication failed: {e}")
    except ServerError as e:
        print(f"✗ Server error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
