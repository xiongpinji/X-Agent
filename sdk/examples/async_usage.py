"""
Example: Async Usage of X-Agent SDK

This example demonstrates:
1. Async client initialization
2. Concurrent task submission
3. Parallel workflow execution
4. Error handling with retry logic
"""

import asyncio
from xagent_sdk import AsyncXAgent
from xagent_sdk.exceptions import RateLimitError, ServiceUnavailableError


async def analyze_repo(client: AsyncXAgent, repo_url: str) -> dict:
    """Analyze a single repository."""
    print(f"Starting analysis for {repo_url}...")

    task = await client.submit_task(
        description=f"Analyze code quality in {repo_url}",
        repo=repo_url,
        params={"max_issues": 5},
    )

    try:
        result = await task.wait(timeout=600, poll_interval=10)
        return {
            "repo": repo_url,
            "status": result.status,
            "result": result.result,
            "duration_ms": result.duration_ms,
        }
    except Exception as e:
        return {
            "repo": repo_url,
            "status": "error",
            "error": str(e),
        }


async def run_concurrent_analysis():
    """Run analysis on multiple repositories concurrently."""
    repositories = [
        "https://github.com/example/project1",
        "https://github.com/example/project2",
        "https://github.com/example/project3",
    ]

    async with AsyncXAgent(
        base_url="http://localhost:8000",
        api_key="your-api-key",
    ) as client:
        # Check health first
        try:
            health = await client.health()
            print(f"✓ Server is {health.status}\n")
        except Exception as e:
            print(f"✗ Cannot connect to server: {e}")
            return

        # Run all analyses concurrently
        print(f"Analyzing {len(repositories)} repositories...\n")
        results = await asyncio.gather(
            *[analyze_repo(client, repo) for repo in repositories],
            return_exceptions=True,
        )

        # Display results
        print("\n=== RESULTS ===\n")
        for result in results:
            if isinstance(result, Exception):
                print(f"✗ Error: {result}")
            else:
                print(f"Repository: {result['repo']}")
                print(f"  Status: {result['status']}")
                print(f"  Duration: {result.get('duration_ms', 'N/A')}ms")

                if result.get("error"):
                    print(f"  Error: {result['error']}")
                elif result.get("result"):
                    print(f"  Result: {result['result']}")
                print()


async def chat_with_retries(max_retries: int = 3):
    """Chat with automatic retry on rate limit."""
    async with AsyncXAgent(api_key="your-api-key") as client:
        message = "Summarize the best practices for API design"

        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}: Sending chat message...")
                response = await client.chat(message)
                print(f"Agent: {response.content}\n")
                return

            except RateLimitError as e:
                wait_time = e.retry_after * (2 ** attempt)
                print(f"Rate limited. Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

            except ServiceUnavailableError:
                if attempt < max_retries - 1:
                    wait_time = 5 * (2 ** attempt)
                    print(f"Service unavailable. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise


async def main():
    """Main entry point."""
    print("=" * 60)
    print("X-Agent SDK - Async Examples")
    print("=" * 60)
    print()

    # Example 1: Concurrent analysis
    print("Example 1: Concurrent Repository Analysis")
    print("-" * 60)
    await run_concurrent_analysis()

    print("\n" + "=" * 60)
    print("Example 2: Chat with Retry Logic")
    print("-" * 60)
    try:
        await chat_with_retries()
    except Exception as e:
        print(f"✗ Chat failed after retries: {e}")


if __name__ == "__main__":
    asyncio.run(main())
