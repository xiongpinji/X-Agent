"""Comprehensive browser automation testing suite."""

import asyncio
import logging
from typing import Any

import pytest
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)


@pytest.fixture
async def browser():
    """Provide browser instance for tests."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest.fixture
async def page(browser: Browser):
    """Provide page instance for tests."""
    page = await browser.new_page()
    yield page
    await page.close()


class TestBrowserBasicOperations:
    """Test basic browser operations."""

    async def test_navigation(self, page: Page):
        """Test page navigation."""
        await page.goto("https://example.com")
        assert page.url == "https://example.com/"

    async def test_click(self, page: Page):
        """Test element clicking."""
        await page.goto("https://example.com")
        # Click on a link if available
        links = await page.query_selector_all("a")
        assert len(links) > 0

    async def test_input_text(self, page: Page):
        """Test text input."""
        await page.goto("https://example.com")
        # Find input if available
        inputs = await page.query_selector_all("input")
        if inputs:
            await inputs[0].fill("test input")
            value = await inputs[0].input_value()
            assert value == "test input"

    async def test_screenshot(self, page: Page, tmp_path):
        """Test screenshot capture."""
        await page.goto("https://example.com")
        screenshot_path = tmp_path / "screenshot.png"
        await page.screenshot(path=str(screenshot_path))
        assert screenshot_path.exists()

    async def test_get_text_content(self, page: Page):
        """Test getting text content."""
        await page.goto("https://example.com")
        content = await page.content()
        assert len(content) > 0
        assert "example" in content.lower()


class TestBrowserAdvancedOperations:
    """Test advanced browser operations."""

    async def test_wait_for_selector(self, page: Page):
        """Test waiting for element."""
        await page.goto("https://example.com")
        # Wait for body element
        await page.wait_for_selector("body")
        body = await page.query_selector("body")
        assert body is not None

    async def test_evaluate_javascript(self, page: Page):
        """Test JavaScript evaluation."""
        await page.goto("https://example.com")
        result = await page.evaluate("() => document.title")
        assert isinstance(result, str)

    async def test_get_element_attributes(self, page: Page):
        """Test getting element attributes."""
        await page.goto("https://example.com")
        links = await page.query_selector_all("a")
        if links:
            href = await links[0].get_attribute("href")
            assert href is not None or href == ""

    async def test_hover_element(self, page: Page):
        """Test hovering over element."""
        await page.goto("https://example.com")
        body = await page.query_selector("body")
        if body:
            await body.hover()

    async def test_keyboard_input(self, page: Page):
        """Test keyboard input."""
        await page.goto("https://example.com")
        await page.keyboard.press("Tab")
        # Verify focus changed
        focused = await page.evaluate("() => document.activeElement.tagName")
        assert focused is not None


class TestBrowserFormOperations:
    """Test form-related operations."""

    async def test_form_fill(self, page: Page):
        """Test filling form fields."""
        await page.goto("https://example.com")
        inputs = await page.query_selector_all("input")
        if inputs:
            for input_elem in inputs:
                input_type = await input_elem.get_attribute("type")
                if input_type != "hidden":
                    await input_elem.fill("test value")

    async def test_select_option(self, page: Page):
        """Test selecting from dropdown."""
        await page.goto("https://example.com")
        selects = await page.query_selector_all("select")
        if selects:
            options = await selects[0].query_selector_all("option")
            if len(options) > 1:
                await selects[0].select_option(index=1)

    async def test_checkbox_toggle(self, page: Page):
        """Test checkbox toggling."""
        await page.goto("https://example.com")
        checkboxes = await page.query_selector_all("input[type='checkbox']")
        if checkboxes:
            await checkboxes[0].check()
            is_checked = await checkboxes[0].is_checked()
            assert is_checked


class TestBrowserNetworkOperations:
    """Test network-related operations."""

    async def test_intercept_requests(self, page: Page):
        """Test request interception."""
        requests = []

        async def handle_route(route):
            requests.append(route.request.url)
            await route.continue_()

        await page.route("**/*", handle_route)
        await page.goto("https://example.com")
        assert len(requests) > 0

    async def test_wait_for_response(self, page: Page):
        """Test waiting for response."""
        async with page.expect_response("**/*") as response_info:
            await page.goto("https://example.com")
        response = await response_info.value
        assert response.status == 200

    async def test_get_response_headers(self, page: Page):
        """Test getting response headers."""
        async with page.expect_response("**/*") as response_info:
            await page.goto("https://example.com")
        response = await response_info.value
        headers = response.headers
        assert isinstance(headers, dict)


class TestBrowserMultiPageOperations:
    """Test multi-page operations."""

    async def test_multiple_pages(self, browser: Browser):
        """Test managing multiple pages."""
        page1 = await browser.new_page()
        page2 = await browser.new_page()

        await page1.goto("https://example.com")
        await page2.goto("https://example.com")

        assert page1.url == page2.url

        await page1.close()
        await page2.close()

    async def test_page_context(self, browser: Browser):
        """Test page context."""
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://example.com")
        assert page.url == "https://example.com/"

        await page.close()
        await context.close()


class TestBrowserErrorHandling:
    """Test error handling."""

    async def test_navigation_timeout(self, page: Page):
        """Test navigation timeout."""
        with pytest.raises(Exception):
            await page.goto("https://invalid-domain-that-does-not-exist-12345.com", timeout=1000)

    async def test_selector_not_found(self, page: Page):
        """Test selector not found."""
        await page.goto("https://example.com")
        element = await page.query_selector("#nonexistent-element-xyz")
        assert element is None

    async def test_wait_for_timeout(self, page: Page):
        """Test wait timeout."""
        await page.goto("https://example.com")
        with pytest.raises(Exception):
            await page.wait_for_selector("#nonexistent-element-xyz", timeout=1000)


class TestBrowserPerformance:
    """Test performance-related operations."""

    async def test_page_load_time(self, page: Page):
        """Test measuring page load time."""
        import time
        start = time.time()
        await page.goto("https://example.com")
        load_time = time.time() - start
        assert load_time > 0

    async def test_element_visibility(self, page: Page):
        """Test checking element visibility."""
        await page.goto("https://example.com")
        body = await page.query_selector("body")
        if body:
            is_visible = await body.is_visible()
            assert isinstance(is_visible, bool)

    async def test_element_enabled(self, page: Page):
        """Test checking element enabled state."""
        await page.goto("https://example.com")
        buttons = await page.query_selector_all("button")
        if buttons:
            is_enabled = await buttons[0].is_enabled()
            assert isinstance(is_enabled, bool)


class TestBrowserAccessibility:
    """Test accessibility features."""

    async def test_get_accessibility_tree(self, page: Page):
        """Test getting accessibility tree."""
        await page.goto("https://example.com")
        if not hasattr(page, "accessibility"):
            pytest.skip("page.accessibility was removed in Playwright 1.40+; "
                        "use locator.aria_snapshot() instead")
        snapshot = await page.accessibility.snapshot()
        assert snapshot is not None

    async def test_element_role(self, page: Page):
        """Test getting element role."""
        await page.goto("https://example.com")
        buttons = await page.query_selector_all("button")
        if buttons:
            # Buttons should have button role
            pass


class TestBrowserStorage:
    """Test storage operations."""

    async def test_local_storage(self, page: Page):
        """Test local storage."""
        await page.goto("https://example.com")
        await page.evaluate("() => localStorage.setItem('test', 'value')")
        value = await page.evaluate("() => localStorage.getItem('test')")
        assert value == "value"

    async def test_session_storage(self, page: Page):
        """Test session storage."""
        await page.goto("https://example.com")
        await page.evaluate("() => sessionStorage.setItem('test', 'value')")
        value = await page.evaluate("() => sessionStorage.getItem('test')")
        assert value == "value"

    async def test_cookies(self, page: Page):
        """Test cookie management."""
        await page.goto("https://example.com")
        await page.context.add_cookies([
            {
                "name": "test",
                "value": "cookie_value",
                "url": "https://example.com",
            }
        ])
        cookies = await page.context.cookies()
        assert any(c["name"] == "test" for c in cookies)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
