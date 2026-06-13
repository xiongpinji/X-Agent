"""
Example: Workflow Execution

This example demonstrates:
1. Workflow template execution
2. Workflow with parameters
3. Waiting for workflow completion
4. Retrieving workflow results
"""

from xagent_sdk import XAgent
from xagent_sdk.models import TaskStatus


def run_code_review_workflow():
    """Execute a code review workflow."""
    client = XAgent(
        base_url="http://localhost:8000",
        api_key="your-api-key",
    )

    try:
        print("Starting code review workflow...\n")

        # Execute workflow and wait for completion
        result = client.workflow_run(
            template="code-review",
            params={
                "repo": "https://github.com/example/project",
                "branch": "feature/new-feature",
                "max_issues": 20,
                "check_security": True,
                "check_performance": True,
            },
            wait=True,
            timeout_seconds=1200,  # 20 minutes
        )

        print(f"Workflow completed!")
        print(f"Status: {result.status}")
        print(f"Duration: {result.duration_ms}ms ({result.duration_ms / 1000 / 60:.1f} min)")

        if result.status == TaskStatus.COMPLETED:
            print(f"\n✓ Review Results:")
            if result.result:
                print(f"  Findings: {result.result}")

            if result.pr_url:
                print(f"  PR: {result.pr_url}")

            if result.diff:
                print(f"  Suggested changes:\n{result.diff}")

        elif result.status == TaskStatus.FAILED:
            print(f"\n✗ Workflow failed: {result.error}")

        elif result.status == TaskStatus.TIMEOUT:
            print(f"\n✗ Workflow timed out")

        return result

    finally:
        client.close()


def run_security_audit_workflow():
    """Execute a security audit workflow."""
    client = XAgent(api_key="your-api-key")

    try:
        print("Starting security audit workflow...\n")

        result = client.workflow_run(
            template="security-audit",
            params={
                "repo": "https://github.com/example/project",
                "severity_threshold": "medium",  # Show medium and above
                "include_dependencies": True,
            },
            wait=True,
            timeout_seconds=900,  # 15 minutes
        )

        print(f"Audit completed!")
        print(f"Status: {result.status}")

        if result.result:
            print(f"Security Issues Found:")
            for issue in result.result.get("issues", []):
                print(f"  - {issue}")

        return result

    finally:
        client.close()


def submit_and_poll_workflow():
    """Submit workflow and manually poll for completion."""
    client = XAgent(api_key="your-api-key")

    try:
        print("Submitting refactoring workflow...\n")

        # Start workflow without waiting
        result = client.workflow_run(
            template="refactor",
            params={
                "repo": "https://github.com/example/project",
                "target_pattern": "*.py",
                "refactoring_type": "modernize-syntax",
            },
            wait=False,  # Don't wait
        )

        task_id = result.task_id if hasattr(result, 'task_id') else None
        print(f"Workflow submitted: {task_id}")

        # Get the task handle for polling
        if task_id:
            task = client.submit_task("dummy")  # Get task handle
            task.task_id = task_id

            # Manual polling
            while not task.is_done:
                poll_result = task.poll()
                print(f"Status: {poll_result.status}, Progress: {poll_result.progress}%")

                if not task.is_done:
                    import time

                    time.sleep(5)

            print(f"\nWorkflow completed: {poll_result.status}")
            return poll_result

    finally:
        client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("X-Agent SDK - Workflow Examples")
    print("=" * 60)
    print()

    print("Example 1: Code Review Workflow (with wait)")
    print("-" * 60)
    try:
        run_code_review_workflow()
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)
    print("Example 2: Security Audit Workflow")
    print("-" * 60)
    try:
        run_security_audit_workflow()
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)
    print("Example 3: Manual Polling")
    print("-" * 60)
    try:
        submit_and_poll_workflow()
    except Exception as e:
        print(f"Error: {e}")
