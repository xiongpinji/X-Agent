"""Usage examples for advanced browser monitoring features."""

from __future__ import annotations

import asyncio
from backend.app.services.browser.advanced_monitoring import advanced_browser_monitoring


async def example_network_monitoring():
    """Example: Monitor network requests and responses."""
    print("=== Network Monitoring Example ===\n")

    # Assuming you have a page object from Playwright
    # page = await browser.new_page()
    # await page.goto("https://example.com")

    # Create a monitoring session
    # session = await advanced_browser_monitoring.create_session("session_1", page)

    # Get all network requests
    # requests = await advanced_browser_monitoring.get_network_requests("session_1")
    # print(f"Total requests: {len(requests)}")
    # for req in requests[:5]:
    #     print(f"  - {req['method']} {req['url']}")

    # Get API requests only
    # api_requests = await advanced_browser_monitoring.get_network_requests(
    #     "session_1",
    #     url_pattern=r"api/.*"
    # )
    # print(f"\nAPI requests: {len(api_requests)}")

    # Get network summary
    # summary = await advanced_browser_monitoring.get_network_summary("session_1")
    # print(f"\nNetwork Summary:")
    # print(f"  Total requests: {summary['total_requests']}")
    # print(f"  Total responses: {summary['total_responses']}")
    # print(f"  Failed responses: {summary['failed_responses']}")
    # print(f"  Average response time: {summary['average_response_time_ms']:.2f}ms")

    # Get failed requests
    # responses = await advanced_browser_monitoring.get_network_responses("session_1")
    # failed = [r for r in responses if r['status'] >= 400]
    # print(f"\nFailed requests: {len(failed)}")
    # for resp in failed:
    #     print(f"  - {resp['status']} {resp['url']}")


async def example_element_references():
    """Example: Use element references for automation."""
    print("=== Element Reference Example ===\n")

    # Create a monitoring session
    # session = await advanced_browser_monitoring.create_session("session_1", page)

    # Build element tree
    # tree = await advanced_browser_monitoring.build_element_tree("session_1")
    # print(f"Total elements: {len(tree['elements'])}")

    # Get specific element
    # elem = await advanced_browser_monitoring.get_element_by_ref("session_1", "ref_1")
    # if elem:
    #     print(f"\nElement ref_1:")
    #     print(f"  Tag: {elem['tag_name']}")
    #     print(f"  Type: {elem['element_type']}")
    #     print(f"  Text: {elem['text']}")
    #     print(f"  Visible: {elem['visible']}")

    # Click element by reference
    # success = await advanced_browser_monitoring.click_by_ref("session_1", "ref_5")
    # print(f"\nClick result: {success}")

    # Fill input by reference
    # success = await advanced_browser_monitoring.fill_by_ref(
    #     "session_1",
    #     "ref_10",
    #     "search query"
    # )
    # print(f"Fill result: {success}")


async def example_console_monitoring():
    """Example: Monitor console messages."""
    print("=== Console Monitoring Example ===\n")

    # Create a monitoring session
    # session = await advanced_browser_monitoring.create_session("session_1", page)

    # Get all console messages
    # messages = await advanced_browser_monitoring.get_console_messages("session_1")
    # print(f"Total console messages: {len(messages)}")
    # for msg in messages[:5]:
    #     print(f"  [{msg['type']}] {msg['text']}")

    # Get only errors
    # errors = await advanced_browser_monitoring.get_console_errors("session_1")
    # print(f"\nConsole errors: {len(errors)}")
    # for error in errors:
    #     print(f"  - {error['text']}")
    #     if error['location']:
    #         print(f"    Location: {error['location']}")

    # Get console summary
    # summary = await advanced_browser_monitoring.get_console_summary("session_1")
    # print(f"\nConsole Summary:")
    # print(f"  Total messages: {summary['total_messages']}")
    # print(f"  Errors: {summary['error_count']}")
    # print(f"  Warnings: {summary['warning_count']}")
    # print(f"  Logs: {summary['log_count']}")

    # Filter messages by pattern
    # api_messages = await advanced_browser_monitoring.get_console_messages(
    #     "session_1",
    #     pattern=r"API.*"
    # )
    # print(f"\nAPI-related messages: {len(api_messages)}")


async def example_natural_language_locator():
    """Example: Find elements using natural language."""
    print("=== Natural Language Locator Example ===\n")

    # Create a monitoring session
    # session = await advanced_browser_monitoring.create_session("session_1", page)

    # Find search button
    # elements = await advanced_browser_monitoring.find_elements_by_description(
    #     "session_1",
    #     "search button",
    #     limit=3
    # )
    # print(f"Found {len(elements)} elements matching 'search button':")
    # for elem in elements:
    #     print(f"  - {elem['selector']}")
    #     print(f"    Confidence: {elem['confidence']:.2f}")
    #     print(f"    Reason: {elem['reason']}")
    #     print(f"    Text: {elem['text']}")

    # Find login form
    # elements = await advanced_browser_monitoring.find_elements_by_description(
    #     "session_1",
    #     "login form",
    #     limit=1
    # )
    # if elements:
    #     print(f"\nFound login form:")
    #     print(f"  Selector: {elements[0]['selector']}")
    #     print(f"  Confidence: {elements[0]['confidence']:.2f}")

    # Find submit button
    # elements = await advanced_browser_monitoring.find_elements_by_description(
    #     "session_1",
    #     "submit",
    #     limit=1
    # )
    # if elements:
    #     print(f"\nFound submit button:")
    #     print(f"  Text: {elements[0]['text']}")


async def example_page_snapshots():
    """Example: Capture and compare page snapshots."""
    print("=== Page Snapshot Example ===\n")

    # Create a monitoring session
    # session = await advanced_browser_monitoring.create_session("session_1", page)

    # Capture initial snapshot
    # snapshot_before = await advanced_browser_monitoring.capture_snapshot(
    #     "session_1",
    #     label="before_action",
    #     include_accessibility=True
    # )
    # print(f"Captured snapshot 'before_action'")
    # print(f"  Title: {snapshot_before['dom']['title']}")
    # print(f"  URL: {snapshot_before['dom']['url']}")

    # Perform some action
    # await page.click("button")
    # await page.wait_for_load_state("networkidle")

    # Capture after snapshot
    # snapshot_after = await advanced_browser_monitoring.capture_snapshot(
    #     "session_1",
    #     label="after_action",
    #     include_accessibility=True
    # )
    # print(f"\nCaptured snapshot 'after_action'")

    # Compare snapshots
    # diff = await advanced_browser_monitoring.compare_snapshots(
    #     "session_1",
    #     "before_action",
    #     "after_action"
    # )
    # print(f"\nSnapshot Comparison:")
    # print(f"  DOM changed: {diff['dom_changed']}")
    # print(f"  Title changed: {diff['title_changed']}")
    # print(f"  URL changed: {diff['url_changed']}")
    # print(f"  Error count increased: {diff['error_count_increased']}")

    # Get DOM diff
    # dom_diff = await advanced_browser_monitoring.get_dom_diff(
    #     "session_1",
    #     "before_action",
    #     "after_action"
    # )
    # if dom_diff:
    #     print(f"\nDOM Diff (first 10 lines):")
    #     for line in dom_diff[:10]:
    #         print(f"  {line}")


async def example_complete_workflow():
    """Example: Complete workflow combining multiple features."""
    print("=== Complete Workflow Example ===\n")

    # This is a pseudo-code example showing how to use all features together

    workflow = """
    # 1. Create session with monitoring
    session = await advanced_browser_monitoring.create_session("session_1", page)

    # 2. Navigate to page
    await page.goto("https://example.com/search")

    # 3. Capture initial state
    await advanced_browser_monitoring.capture_snapshot(
        "session_1",
        label="initial"
    )

    # 4. Find search input using natural language
    elements = await advanced_browser_monitoring.find_elements_by_description(
        "session_1",
        "search input",
        limit=1
    )

    # 5. Build element tree to get references
    tree = await advanced_browser_monitoring.build_element_tree("session_1")

    # 6. Fill search input
    if elements:
        await page.fill(elements[0]['selector'], "test query")

    # 7. Find and click search button
    buttons = await advanced_browser_monitoring.find_elements_by_description(
        "session_1",
        "search button",
        limit=1
    )
    if buttons:
        await page.click(buttons[0]['selector'])

    # 8. Wait for results
    await page.wait_for_load_state("networkidle")

    # 9. Capture final state
    await advanced_browser_monitoring.capture_snapshot(
        "session_1",
        label="after_search"
    )

    # 10. Compare states
    diff = await advanced_browser_monitoring.compare_snapshots(
        "session_1",
        "initial",
        "after_search"
    )
    print(f"Page changed: {diff['dom_changed']}")

    # 11. Check for errors
    errors = await advanced_browser_monitoring.get_console_errors("session_1")
    if errors:
        print(f"Found {len(errors)} console errors")

    # 12. Get network summary
    summary = await advanced_browser_monitoring.get_network_summary("session_1")
    print(f"Network requests: {summary['total_requests']}")
    print(f"Failed requests: {summary['failed_responses']}")

    # 13. Close session
    await advanced_browser_monitoring.close_session("session_1")
    """

    print(workflow)


async def main():
    """Run all examples."""
    print("Advanced Browser Monitoring Examples\n")
    print("=" * 50 + "\n")

    # Note: These examples are pseudo-code and require actual Playwright setup
    # Uncomment the actual code when you have a real page object

    await example_network_monitoring()
    print("\n" + "=" * 50 + "\n")

    await example_element_references()
    print("\n" + "=" * 50 + "\n")

    await example_console_monitoring()
    print("\n" + "=" * 50 + "\n")

    await example_natural_language_locator()
    print("\n" + "=" * 50 + "\n")

    await example_page_snapshots()
    print("\n" + "=" * 50 + "\n")

    await example_complete_workflow()


if __name__ == "__main__":
    asyncio.run(main())
