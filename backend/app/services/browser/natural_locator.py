"""Natural language element locator for browser automation."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

try:
    from playwright.async_api import Locator, Page
except ImportError:
    Page = Locator = object  # type: ignore[assignment]


@dataclass
class LocatedElement:
    """Represents a located element with confidence score."""
    locator: Locator
    selector: str
    confidence: float
    reason: str
    text: str | None = None
    tag_name: str | None = None


class NaturalLocator:
    """Locates elements using natural language descriptions."""

    def __init__(self, page: Page | None = None):
        self.page = page

    async def find_element(self, page: Page, description: str) -> LocatedElement | None:
        """Find a single element matching the description."""
        self.page = page
        elements = await self.find_elements(page, description, limit=1)
        return elements[0] if elements else None

    async def find_elements(
        self,
        page: Page,
        description: str,
        limit: int = 5,
    ) -> list[LocatedElement]:
        """Find multiple elements matching the description."""
        self.page = page
        candidates = []

        # Strategy 1: Text matching
        text_candidates = await self._find_by_text(page, description)
        candidates.extend(text_candidates)

        # Strategy 2: ARIA label matching
        aria_candidates = await self._find_by_aria_label(page, description)
        candidates.extend(aria_candidates)

        # Strategy 3: Placeholder matching
        placeholder_candidates = await self._find_by_placeholder(page, description)
        candidates.extend(placeholder_candidates)

        # Strategy 4: Title attribute matching
        title_candidates = await self._find_by_title(page, description)
        candidates.extend(title_candidates)

        # Strategy 5: Button/link by role
        role_candidates = await self._find_by_role(page, description)
        candidates.extend(role_candidates)

        # Deduplicate and sort by confidence
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate.selector not in seen:
                seen.add(candidate.selector)
                unique_candidates.append(candidate)

        unique_candidates.sort(key=lambda x: x.confidence, reverse=True)
        return unique_candidates[:limit]

    async def _find_by_text(self, page: Page, description: str) -> list[LocatedElement]:
        """Find elements by text content."""
        candidates = []

        # Try exact match first
        try:
            locators = page.locator(f"text={description}")
            count = await locators.count()
            if count > 0:
                for i in range(min(count, 5)):
                    try:
                        locator = locators.nth(i)
                        text = await locator.text_content()
                        tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                        candidates.append(
                            LocatedElement(
                                locator=locator,
                                selector=f"text={description}",
                                confidence=1.0,
                                reason="exact_text_match",
                                text=text,
                                tag_name=tag,
                            )
                        )
                    except Exception:
                        pass
        except Exception:
            pass

        # Try partial match
        try:
            # Get all interactive elements
            for selector in ["button", "a", "input", "[role='button']", "[role='link']"]:
                try:
                    locators = page.locator(selector)
                    count = await locators.count()
                    for i in range(min(count, 10)):
                        try:
                            locator = locators.nth(i)
                            text = await locator.text_content()
                            if text and self._similarity(text.lower(), description.lower()) > 0.6:
                                tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                                confidence = self._similarity(text.lower(), description.lower())
                                candidates.append(
                                    LocatedElement(
                                        locator=locator,
                                        selector=selector,
                                        confidence=confidence,
                                        reason="partial_text_match",
                                        text=text,
                                        tag_name=tag,
                                    )
                                )
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        return candidates

    async def _find_by_aria_label(self, page: Page, description: str) -> list[LocatedElement]:
        """Find elements by ARIA label."""
        candidates = []

        try:
            locators = page.locator(f"[aria-label*='{description}']")
            count = await locators.count()
            for i in range(min(count, 5)):
                try:
                    locator = locators.nth(i)
                    aria_label = await locator.get_attribute("aria-label")
                    tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                    confidence = self._similarity(
                        (aria_label or "").lower(),
                        description.lower(),
                    )
                    candidates.append(
                        LocatedElement(
                            locator=locator,
                            selector=f"[aria-label*='{description}']",
                            confidence=confidence,
                            reason="aria_label_match",
                            text=aria_label,
                            tag_name=tag,
                        )
                    )
                except Exception:
                    pass
        except Exception:
            pass

        return candidates

    async def _find_by_placeholder(self, page: Page, description: str) -> list[LocatedElement]:
        """Find elements by placeholder attribute."""
        candidates = []

        try:
            locators = page.locator(f"[placeholder*='{description}']")
            count = await locators.count()
            for i in range(min(count, 5)):
                try:
                    locator = locators.nth(i)
                    placeholder = await locator.get_attribute("placeholder")
                    tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                    confidence = self._similarity(
                        (placeholder or "").lower(),
                        description.lower(),
                    )
                    candidates.append(
                        LocatedElement(
                            locator=locator,
                            selector=f"[placeholder*='{description}']",
                            confidence=confidence,
                            reason="placeholder_match",
                            text=placeholder,
                            tag_name=tag,
                        )
                    )
                except Exception:
                    pass
        except Exception:
            pass

        return candidates

    async def _find_by_title(self, page: Page, description: str) -> list[LocatedElement]:
        """Find elements by title attribute."""
        candidates = []

        try:
            locators = page.locator(f"[title*='{description}']")
            count = await locators.count()
            for i in range(min(count, 5)):
                try:
                    locator = locators.nth(i)
                    title = await locator.get_attribute("title")
                    tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                    confidence = self._similarity(
                        (title or "").lower(),
                        description.lower(),
                    )
                    candidates.append(
                        LocatedElement(
                            locator=locator,
                            selector=f"[title*='{description}']",
                            confidence=confidence,
                            reason="title_match",
                            text=title,
                            tag_name=tag,
                        )
                    )
                except Exception:
                    pass
        except Exception:
            pass

        return candidates

    async def _find_by_role(self, page: Page, description: str) -> list[LocatedElement]:
        """Find elements by role."""
        candidates = []

        # Map common descriptions to roles
        role_map = {
            "search": "searchbox",
            "button": "button",
            "link": "link",
            "menu": "menu",
            "tab": "tab",
            "checkbox": "checkbox",
            "radio": "radio",
        }

        for desc_key, role in role_map.items():
            if desc_key.lower() in description.lower():
                try:
                    locators = page.locator(f"[role='{role}']")
                    count = await locators.count()
                    for i in range(min(count, 3)):
                        try:
                            locator = locators.nth(i)
                            text = await locator.text_content()
                            tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                            candidates.append(
                                LocatedElement(
                                    locator=locator,
                                    selector=f"[role='{role}']",
                                    confidence=0.7,
                                    reason=f"role_match_{role}",
                                    text=text,
                                    tag_name=tag,
                                )
                            )
                        except Exception:
                            pass
                except Exception:
                    pass

        return candidates

    def _similarity(self, a: str, b: str) -> float:
        """Calculate similarity between two strings (0-1)."""
        return SequenceMatcher(None, a, b).ratio()
