"""
Usage examples and best practices for enhanced browser automation.

Demonstrates how to use all advanced capabilities effectively.
"""

import asyncio
from backend.app.services.browser.enhanced_service import EnhancedBrowserAutomationService
from backend.app.services.browser.waiter import WaitStrategy
from backend.app.services.browser.stealth import StealthBrowser


# ============================================================================
# Example 1: Basic Navigation and Interaction
# ============================================================================

async def example_basic_navigation():
    """
    Basic example: Navigate to a page and interact with elements.
    """
    service = EnhancedBrowserAutomationService()

    try:
        # Create a session
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        session = await service.create_session("session_1", page)

        # Navigate to page
        await service.navigate(session.session_id, "https://example.com")

        # Find and click button
        await service.find_and_click(session.session_id, "button.submit")

        # Fill form field
        await service.find_and_fill(
            session.session_id,
            "input[name='email']",
            "user@example.com",
        )

        # Take screenshot
        screenshot = await service.take_screenshot(
            session.session_id,
            path="/tmp/screenshot.png",
        )

        # Get session stats
        stats = service.get_session_stats(session.session_id)
        print(f"Session stats: {stats}")

    finally:
        await service.cleanup()


# ============================================================================
# Example 2: Smart Element Locating with Multiple Strategies
# ============================================================================

async def example_smart_locating():
    """
    Example: Use smart locator with multiple strategies and fallback.
    """
    from backend.app.services.browser.smart_locator import SmartLocator, LocatorStrategy

    locator = SmartLocator("session_1", max_retries=3)

    # Try multiple strategies in order
    result = locator.find_element(
        strategies=[
            LocatorStrategy.CSS,
            LocatorStrategy.XPATH,
            LocatorStrategy.TEXT,
        ],
        css_selector=".primary-button",
        xpath="//button[@class='primary-button']",
        text="Submit",
        fallback_to_ai=True,
        use_cache=True,
    )

    if result.found:
        print(f"Element found using {result.strategy_used.value}")
        print(f"Time taken: {result.time_taken_ms:.2f}ms")
    else:
        print(f"Element not found: {result.error}")

    # Get cache statistics
    stats = locator.get_cache_stats()
    print(f"Cache stats: {stats}")


# ============================================================================
# Example 3: Intelligent Waiting with Adaptive Strategy
# ============================================================================

async def example_smart_waiting():
    """
    Example: Use smart waiter with adaptive waiting strategy.
    """
    from backend.app.services.browser.waiter import SmartWaiter
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()

    waiter = SmartWaiter("session_1", default_timeout=30.0)

    try:
        # Wait for selector with adaptive strategy
        result = await waiter.wait_for_selector(
            page,
            ".dynamic-content",
            strategy=WaitStrategy.ADAPTIVE,
        )

        if result.success:
            print(f"Element appeared after {result.time_taken_ms:.2f}ms")
        else:
            print(f"Wait failed: {result.reason}")

        # Wait for page to become stable
        result = await waiter.wait_for_page_stable(
            page,
            stability_threshold=1.0,
        )

        if result.success:
            print("Page is now stable")

        # Wait for custom condition
        def custom_condition(p):
            # Check if specific element is visible
            return True

        result = await waiter.wait_for_condition(
            page,
            custom_condition,
            timeout=10.0,
        )

        # Get wait statistics
        stats = waiter.get_wait_stats()
        print(f"Wait stats: {stats}")

    finally:
        await page.close()
        await context.close()
        await browser.close()


# ============================================================================
# Example 4: Advanced Interactions
# ============================================================================

async def example_advanced_interactions():
    """
    Example: Use advanced interactions like drag & drop, file upload, etc.
    """
    from backend.app.services.browser.interactions import AdvancedInteractions
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()

    interactions = AdvancedInteractions("session_1")

    try:
        # Drag and drop
        result = await interactions.drag_and_drop(
            page,
            ".draggable-item",
            ".drop-zone",
        )
        print(f"Drag and drop: {result.success}")

        # Hover element
        result = await interactions.hover_element(
            page,
            ".menu-item",
            duration_ms=500,
        )
        print(f"Hover: {result.success}")

        # Scroll to element
        result = await interactions.scroll_to_element(
            page,
            ".target-element",
            smooth=True,
        )
        print(f"Scroll: {result.success}")

        # Type text with delay
        result = await interactions.type_text(
            page,
            "input[name='search']",
            "search query",
            delay_ms=50,
        )
        print(f"Type: {result.success}")

        # Double click
        result = await interactions.double_click(
            page,
            ".editable-cell",
        )
        print(f"Double click: {result.success}")

        # Right click
        result = await interactions.right_click(
            page,
            ".context-menu-target",
        )
        print(f"Right click: {result.success}")

        # Get interaction statistics
        stats = interactions.get_interaction_stats()
        print(f"Interaction stats: {stats}")

    finally:
        await page.close()
        await context.close()
        await browser.close()


# ============================================================================
# Example 5: Page Analysis and Data Extraction
# ============================================================================

async def example_page_analysis():
    """
    Example: Analyze page structure and extract data.
    """
    from backend.app.services.browser.analyzer import PageAnalyzer
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()

    analyzer = PageAnalyzer("session_1")

    try:
        await page.goto("https://example.com")

        # Analyze page structure
        structure = await analyzer.analyze_page(page)

        print(f"Page title: {structure.title}")
        print(f"Buttons found: {len(structure.buttons)}")
        print(f"Links found: {len(structure.links)}")
        print(f"Forms found: {len(structure.forms)}")
        print(f"Input fields: {len(structure.inputs)}")

        # Extract text from element
        text = await analyzer.extract_text_content(page, "h1")
        print(f"Heading text: {text}")

        # Extract table data
        table_data = await analyzer.extract_table_data(page, "table")
        print(f"Table rows: {len(table_data)}")

    finally:
        await page.close()
        await context.close()
        await browser.close()


# ============================================================================
# Example 6: Error Recovery and Resilience
# ============================================================================

async def example_error_recovery():
    """
    Example: Handle errors with automatic recovery.
    """
    from backend.app.services.browser.recovery import ErrorRecovery, ErrorType
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()

    recovery = ErrorRecovery("session_1")

    try:
        # Detect CAPTCHA
        has_captcha = await recovery.detect_captcha(page)
        print(f"CAPTCHA detected: {has_captcha}")

        # Detect login requirement
        login_required = await recovery.detect_login_required(page)
        print(f"Login required: {login_required}")

        # Detect page crash
        page_crashed = await recovery.detect_page_crash(page)
        print(f"Page crashed: {page_crashed}")

        # Retry operation with exponential backoff
        async def risky_operation():
            # Simulate operation that might fail
            return "success"

        result = await recovery.retry_operation(
            risky_operation,
            max_retries=3,
            delay=1.0,
            backoff=True,
        )
        print(f"Operation result: {result}")

        # Get error statistics
        stats = recovery.get_error_stats()
        print(f"Error stats: {stats}")

    finally:
        await page.close()
        await context.close()
        await browser.close()


# ============================================================================
# Example 7: Browser Pool Management
# ============================================================================

async def example_browser_pool():
    """
    Example: Use browser pool for efficient resource management.
    """
    from backend.app.services.browser.pool import create_browser_pool

    # Create a browser pool
    pool = create_browser_pool("main_pool", max_browsers=5)

    try:
        # Acquire browser from pool
        browser = await pool.acquire_browser()
        if browser:
            print(f"Acquired browser: {browser.browser_id}")

            # Use browser...

            # Release browser back to pool
            await pool.release_browser(browser.browser_id)
            print(f"Released browser: {browser.browser_id}")

        # Get pool statistics
        stats = pool.get_stats()
        print(f"Pool stats: {stats}")

        # Cleanup idle browsers
        closed = await pool.cleanup_idle_browsers()
        print(f"Closed {closed} idle browsers")

        # Health check
        healthy = await pool.health_check()
        print(f"Pool health: {'OK' if healthy else 'ISSUES'}")

    finally:
        await pool.close_all()


# ============================================================================
# Example 8: Stealth Mode and Anti-Detection
# ============================================================================

async def example_stealth_mode():
    """
    Example: Use stealth mode to avoid detection.
    """
    from backend.app.services.browser.stealth import StealthBrowser
    from playwright.async_api import async_playwright

    stealth = StealthBrowser("session_1")

    # Get stealth context options
    context_options = stealth.get_stealth_context_options()
    print(f"Context options: {context_options}")

    # Get stealth launch options
    launch_options = stealth.get_stealth_launch_options()
    print(f"Launch options: {launch_options}")

    # Create browser with stealth options
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(**launch_options)
    context = await browser.new_context(**context_options)
    page = await context.new_page()

    try:
        # Apply stealth measures
        await stealth.apply_stealth_measures(page)

        # Get random user agent
        ua = stealth.get_random_user_agent()
        print(f"User agent: {ua.browser} on {ua.os}")

        # Simulate human behavior
        await stealth.simulate_human_behavior(page)

        # Add delay between actions
        await stealth.add_delay_between_actions(min_delay=1.0, max_delay=3.0)

    finally:
        await page.close()
        await context.close()
        await browser.close()


# ============================================================================
# Example 9: Complete Workflow
# ============================================================================

async def example_complete_workflow():
    """
    Example: Complete workflow combining all features.
    """
    service = EnhancedBrowserAutomationService(
        pool_size=5,
        default_timeout=30.0,
        enable_stealth=True,
    )

    try:
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Create session
        session = await service.create_session("workflow_session", page)

        # 1. Navigate with smart waiting
        await service.navigate(
            session.session_id,
            "https://example.com",
            wait_strategy=WaitStrategy.ADAPTIVE,
        )

        # 2. Analyze page
        structure = await service.analyze_page(session.session_id)
        print(f"Found {len(structure.buttons)} buttons")

        # 3. Interact with elements
        await service.find_and_click(session.session_id, "button.search")
        await service.find_and_fill(
            session.session_id,
            "input[name='q']",
            "search term",
        )

        # 4. Extract data
        text = await service.extract_text(session.session_id, ".results")
        print(f"Results: {text}")

        # 5. Take screenshot
        await service.take_screenshot(session.session_id, "/tmp/result.png")

        # 6. Get statistics
        stats = service.get_session_stats(session.session_id)
        print(f"Session completed: {stats['action_count']} actions")

    finally:
        await service.cleanup()


# ============================================================================
# Best Practices
# ============================================================================

"""
BEST PRACTICES FOR ENHANCED BROWSER AUTOMATION:

1. SESSION MANAGEMENT:
   - Always use try/finally to ensure cleanup
   - Create sessions for each independent task
   - Monitor session statistics for performance

2. ELEMENT LOCATING:
   - Use multiple strategies for robustness
   - Enable caching for repeated elements
   - Implement fallback strategies

3. WAITING:
   - Use adaptive waiting for dynamic content
   - Set appropriate timeouts based on page complexity
   - Monitor wait statistics to optimize timeouts

4. INTERACTIONS:
   - Use appropriate interaction types (click, hover, drag)
   - Add delays between actions to simulate human behavior
   - Handle iframe interactions explicitly

5. ERROR HANDLING:
   - Register custom error handlers for specific scenarios
   - Use retry with exponential backoff for transient errors
   - Detect and handle CAPTCHA and login requirements

6. RESOURCE MANAGEMENT:
   - Use browser pool for multiple concurrent sessions
   - Monitor pool statistics and health
   - Cleanup idle browsers regularly

7. STEALTH MODE:
   - Enable stealth for sites with bot detection
   - Randomize user agents and viewports
   - Simulate human-like behavior

8. PERFORMANCE:
   - Cache element locations when possible
   - Use appropriate wait strategies
   - Monitor and optimize timeout values
   - Use browser pool for concurrent operations

9. DEBUGGING:
   - Enable logging for troubleshooting
   - Take screenshots on errors
   - Monitor interaction and error statistics
   - Review session statistics

10. TESTING:
    - Write comprehensive tests for automation workflows
    - Test error recovery scenarios
    - Validate page analysis results
    - Monitor success rates
"""


if __name__ == "__main__":
    # Run examples
    print("Example 1: Basic Navigation")
    asyncio.run(example_basic_navigation())

    print("\nExample 2: Smart Locating")
    asyncio.run(example_smart_locating())

    print("\nExample 3: Smart Waiting")
    asyncio.run(example_smart_waiting())

    print("\nExample 4: Advanced Interactions")
    asyncio.run(example_advanced_interactions())

    print("\nExample 5: Page Analysis")
    asyncio.run(example_page_analysis())

    print("\nExample 6: Error Recovery")
    asyncio.run(example_error_recovery())

    print("\nExample 7: Browser Pool")
    asyncio.run(example_browser_pool())

    print("\nExample 8: Stealth Mode")
    asyncio.run(example_stealth_mode())

    print("\nExample 9: Complete Workflow")
    asyncio.run(example_complete_workflow())
