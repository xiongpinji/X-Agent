# 未接线（P0-11 审计标注）：本模块为宣传的企业级浏览器增强能力，但当前没有任何 API 消费方，未暴露到任何接口。按要求保留代码，待后续接线或归档。
"""
Anti-detection and stealth mechanisms for browser automation.

Implements User-Agent rotation, fingerprint randomization, WebDriver hiding,
and behavior simulation.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UserAgent:
    """User agent information."""
    user_agent: str
    browser: str
    os: str
    device: str


class StealthBrowser:
    """
    Implements stealth techniques to avoid detection.
    """

    # Common user agents
    USER_AGENTS = [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]

    # Screen resolutions
    SCREEN_RESOLUTIONS = [
        (1920, 1080),
        (1366, 768),
        (1440, 900),
        (1536, 864),
        (1280, 720),
        (2560, 1440),
        (1024, 768),
    ]

    # Languages
    LANGUAGES = [
        "en-US",
        "en-GB",
        "de-DE",
        "fr-FR",
        "es-ES",
        "it-IT",
        "ja-JP",
        "zh-CN",
        "ru-RU",
    ]

    def __init__(self, session_id: str):
        """
        Initialize stealth browser.

        Args:
            session_id: Browser session ID
        """
        self.session_id = session_id
        self.logger = logger
        self.current_user_agent: UserAgent | None = None
        self.current_resolution: tuple | None = None
        self.current_language: str | None = None

    async def apply_stealth_measures(self, page: Any) -> bool:
        """
        Apply all stealth measures to a page.

        Args:
            page: Playwright page object

        Returns:
            True if successful
        """
        try:
            # Hide WebDriver
            await self._hide_webdriver(page)

            # Randomize fingerprint
            await self._randomize_fingerprint(page)

            # Inject stealth scripts
            await self._inject_stealth_scripts(page)

            self.logger.info("Stealth measures applied")
            return True

        except Exception as e:
            self.logger.error(f"Failed to apply stealth measures: {e}")
            return False

    async def _hide_webdriver(self, page: Any) -> None:
        """Hide WebDriver detection."""
        try:
            # Override navigator.webdriver
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
            """)

            # Override chrome detection
            await page.add_init_script("""
                window.chrome = {
                    runtime: {}
                };
            """)

            self.logger.debug("WebDriver hidden")
        except Exception as e:
            self.logger.warning(f"Failed to hide WebDriver: {e}")

    async def _randomize_fingerprint(self, page: Any) -> None:
        """Randomize browser fingerprint."""
        try:
            # Randomize screen resolution
            resolution = random.choice(self.SCREEN_RESOLUTIONS)
            self.current_resolution = resolution

            # Randomize language
            language = random.choice(self.LANGUAGES)
            self.current_language = language

            # Inject fingerprint randomization
            await page.add_init_script(f"""
                Object.defineProperty(screen, 'width', {{
                    get: () => {resolution[0]},
                }});
                Object.defineProperty(screen, 'height', {{
                    get: () => {resolution[1]},
                }});
                Object.defineProperty(navigator, 'language', {{
                    get: () => '{language}',
                }});
                Object.defineProperty(navigator, 'languages', {{
                    get: () => ['{language}'],
                }});
            """)

            self.logger.debug(f"Fingerprint randomized: {resolution}, {language}")
        except Exception as e:
            self.logger.warning(f"Failed to randomize fingerprint: {e}")

    async def _inject_stealth_scripts(self, page: Any) -> None:
        """Inject stealth scripts."""
        try:
            # Prevent headless detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' })
                    }),
                });
            """)

            # Randomize timezone
            await page.add_init_script("""
                const timezones = [
                    'America/New_York',
                    'America/Chicago',
                    'America/Denver',
                    'America/Los_Angeles',
                    'Europe/London',
                    'Europe/Paris',
                    'Asia/Tokyo',
                ];
                const tz = timezones[Math.floor(Math.random() * timezones.length)];
                Intl.DateTimeFormat.prototype.resolvedOptions = function() {
                    return { timeZone: tz };
                };
            """)

            self.logger.debug("Stealth scripts injected")
        except Exception as e:
            self.logger.warning(f"Failed to inject stealth scripts: {e}")

    def get_random_user_agent(self) -> UserAgent:
        """Get a random user agent."""
        ua_string = random.choice(self.USER_AGENTS)

        # Parse user agent
        if "Chrome" in ua_string and "Edg" not in ua_string:
            browser = "Chrome"
        elif "Firefox" in ua_string:
            browser = "Firefox"
        elif "Safari" in ua_string and "Chrome" not in ua_string:
            browser = "Safari"
        elif "Edg" in ua_string:
            browser = "Edge"
        else:
            browser = "Unknown"

        if "Windows" in ua_string:
            os = "Windows"
        elif "Macintosh" in ua_string:
            os = "macOS"
        elif "Linux" in ua_string:
            os = "Linux"
        else:
            os = "Unknown"

        device = "Mobile" if "Mobile" in ua_string else "Desktop"

        user_agent = UserAgent(
            user_agent=ua_string,
            browser=browser,
            os=os,
            device=device,
        )

        self.current_user_agent = user_agent
        return user_agent

    def get_random_viewport(self) -> dict:
        """Get random viewport settings."""
        width, height = random.choice(self.SCREEN_RESOLUTIONS)
        return {
            "width": width,
            "height": height,
        }

    def get_random_locale(self) -> str:
        """Get random locale."""
        return random.choice(self.LANGUAGES)

    async def simulate_human_behavior(self, page: Any) -> None:
        """Simulate human-like behavior."""
        try:
            import asyncio

            # Random mouse movements
            await page.mouse.move(
                random.randint(100, 1000),
                random.randint(100, 600),
            )
            await asyncio.sleep(random.uniform(0.5, 2.0))

            # Random scrolling
            await page.evaluate(f"""
                window.scrollBy(0, {random.randint(100, 500)});
            """)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            self.logger.debug("Human behavior simulated")
        except Exception as e:
            self.logger.warning(f"Failed to simulate human behavior: {e}")

    async def add_delay_between_actions(self, min_delay: float = 0.5, max_delay: float = 2.0) -> None:
        """Add random delay between actions."""
        import asyncio
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    def get_stealth_context_options(self) -> dict:
        """Get context options for stealth mode."""
        user_agent = self.get_random_user_agent()
        viewport = self.get_random_viewport()
        locale = self.get_random_locale()

        return {
            "user_agent": user_agent.user_agent,
            "viewport": viewport,
            "locale": locale,
            "timezone_id": random.choice([
                "America/New_York",
                "Europe/London",
                "Asia/Tokyo",
            ]),
            "geolocation": {
                "latitude": random.uniform(-90, 90),
                "longitude": random.uniform(-180, 180),
            },
            "permissions": ["geolocation"],
            "ignore_https_errors": True,
        }

    def get_stealth_launch_options(self) -> dict:
        """Get launch options for stealth mode."""
        return {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-popup-blocking",
                "--disable-prompt-on-repost",
                "--disable-background-networking",
                "--disable-client-side-phishing-detection",
                "--disable-component-extensions-with-background-pages",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-features=TranslateUI",
                "--disable-sync",
            ],
        }


def create_stealth_browser(session_id: str) -> StealthBrowser:
    """Create a stealth browser."""
    return StealthBrowser(session_id)
