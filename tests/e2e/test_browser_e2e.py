"""Browser E2E tests using Playwright (requires: pip install pytest-playwright).

Run with: pytest tests/e2e/test_browser_e2e.py --browser chromium
Requires: Backend running on localhost:8000, Frontend on localhost:3000
"""
import pytest

playwright_available = False
try:
    from playwright.sync_api import Page, expect
    playwright_available = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(not playwright_available, reason="pytest-playwright not installed")


@pytest.fixture(scope="session")
def base_url():
    return "http://localhost:3000"


class TestBrowserE2E:
    def test_homepage_loads(self, page: "Page", base_url: str):
        page.goto(base_url)
        expect(page).to_have_title_containing("X-Agent")

    def test_navigation_works(self, page: "Page", base_url: str):
        page.goto(base_url)
        page.click("text=Goals")
        expect(page).to_have_url(f"{base_url}/goals")

    def test_goal_creation(self, page: "Page", base_url: str):
        page.goto(f"{base_url}/goals")
        page.fill("input[placeholder*='goal']", "Test E2E goal")
        page.click("button:has-text('Create')")
        expect(page.locator("text=Test E2E goal")).to_be_visible()
