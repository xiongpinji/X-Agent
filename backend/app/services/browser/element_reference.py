"""Element reference system for browser automation with accessibility tree support."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

try:
    from playwright.async_api import ElementHandle, Locator, Page
except ImportError:
    Page = Locator = ElementHandle = object  # type: ignore[assignment]


class ElementType(StrEnum):
    """Types of elements."""
    BUTTON = "button"
    INPUT = "input"
    LINK = "link"
    TEXT = "text"
    IMAGE = "image"
    FORM = "form"
    HEADING = "heading"
    LIST = "list"
    TABLE = "table"
    DIALOG = "dialog"
    OTHER = "other"


@dataclass
class ElementAttribute:
    """Represents an element attribute."""
    name: str
    value: str


@dataclass
class ElementReference:
    """Represents a reference to a page element."""
    ref: str  # e.g., "ref_1", "ref_2"
    tag_name: str
    element_type: ElementType
    text: str = ""
    attributes: list[ElementAttribute] = field(default_factory=list)
    aria_label: str | None = None
    aria_role: str | None = None
    placeholder: str | None = None
    title: str | None = None
    visible: bool = True
    enabled: bool = True
    bounding_box: dict[str, float] | None = None
    selector: str | None = None
    xpath: str | None = None
    children_count: int = 0
    parent_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "tag_name": self.tag_name,
            "element_type": self.element_type.value,
            "text": self.text,
            "attributes": [{"name": a.name, "value": a.value} for a in self.attributes],
            "aria_label": self.aria_label,
            "aria_role": self.aria_role,
            "placeholder": self.placeholder,
            "title": self.title,
            "visible": self.visible,
            "enabled": self.enabled,
            "bounding_box": self.bounding_box,
            "selector": self.selector,
            "xpath": self.xpath,
            "children_count": self.children_count,
            "parent_ref": self.parent_ref,
        }


@dataclass
class ElementTree:
    """Represents the accessibility tree of a page."""
    root: ElementReference
    elements: dict[str, ElementReference] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    def get_element(self, ref: str) -> ElementReference | None:
        """Get an element by reference."""
        return self.elements.get(ref)

    def get_children(self, ref: str) -> list[ElementReference]:
        """Get all children of an element."""
        return [e for e in self.elements.values() if e.parent_ref == ref]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root.to_dict(),
            "elements": {ref: elem.to_dict() for ref, elem in self.elements.items()},
            "timestamp": self.timestamp,
        }


class ElementReferenceSystem:
    """Manages element references and accessibility tree for a page."""

    def __init__(self, page: Page | None = None):
        self.page = page
        self._ref_counter = 0
        self._element_map: dict[str, Any] = {}  # ref -> element handle
        self._tree: ElementTree | None = None

    async def build_element_tree(self, page: Page) -> ElementTree:
        """Build the accessibility tree for the page."""
        self.page = page
        self._ref_counter = 0
        self._element_map.clear()

        # Get all interactive elements
        elements = await self._extract_elements(page)

        if not elements:
            # Create a minimal root
            root = ElementReference(
                ref="ref_0",
                tag_name="html",
                element_type=ElementType.OTHER,
                text="",
            )
            self._tree = ElementTree(root=root)
            return self._tree

        # Build tree structure
        tree = ElementTree(root=elements[0])
        for elem in elements:
            tree.elements[elem.ref] = elem

        self._tree = tree
        return tree

    async def _extract_elements(self, page: Page) -> list[ElementReference]:
        """Extract all interactive elements from the page."""
        elements = []

        # Query for interactive elements
        selectors = [
            "button", "a", "input", "select", "textarea",
            "[role='button']", "[role='link']", "[role='menuitem']",
            "[onclick]", "label", "h1", "h2", "h3", "h4", "h5", "h6",
        ]

        ref_id = 0
        for selector in selectors:
            try:
                locators = page.locator(selector)
                count = await locators.count()

                for i in range(min(count, 100)):  # Limit to 100 per selector
                    try:
                        locator = locators.nth(i)
                        elem = await self._extract_element_info(locator, f"ref_{ref_id}")
                        if elem:
                            elements.append(elem)
                            ref_id += 1
                    except Exception:
                        pass
            except Exception:
                pass

        return elements

    async def _extract_element_info(self, locator: Locator, ref: str) -> ElementReference | None:
        """Extract information about an element."""
        try:
            tag_name = await locator.evaluate("el => el.tagName.toLowerCase()")
            text = await locator.text_content()
            text = (text or "").strip()[:200]  # Limit text length

            # Get attributes
            attributes = []
            for attr in ["id", "class", "name", "type", "value", "href", "src"]:
                try:
                    val = await locator.get_attribute(attr)
                    if val:
                        attributes.append(ElementAttribute(name=attr, value=val))
                except Exception:
                    pass

            # Get ARIA attributes
            aria_label = await locator.get_attribute("aria-label")
            aria_role = await locator.get_attribute("role")
            placeholder = await locator.get_attribute("placeholder")
            title = await locator.get_attribute("title")

            # Check visibility and enabled state
            visible = await locator.is_visible()
            enabled = await locator.is_enabled()

            # Get bounding box
            box = await locator.bounding_box()
            bounding_box = None
            if box:
                bounding_box = {
                    "x": box["x"],
                    "y": box["y"],
                    "width": box["width"],
                    "height": box["height"],
                }

            # Determine element type
            element_type = self._determine_element_type(tag_name, aria_role)

            elem = ElementReference(
                ref=ref,
                tag_name=tag_name,
                element_type=element_type,
                text=text,
                attributes=attributes,
                aria_label=aria_label,
                aria_role=aria_role,
                placeholder=placeholder,
                title=title,
                visible=visible,
                enabled=enabled,
                bounding_box=bounding_box,
            )

            self._element_map[ref] = locator
            return elem
        except Exception:
            return None

    def _determine_element_type(self, tag_name: str, aria_role: str | None) -> ElementType:
        """Determine the type of element."""
        if aria_role:
            role_map = {
                "button": ElementType.BUTTON,
                "link": ElementType.LINK,
                "menuitem": ElementType.BUTTON,
                "tab": ElementType.BUTTON,
            }
            if aria_role in role_map:
                return role_map[aria_role]

        tag_map = {
            "button": ElementType.BUTTON,
            "a": ElementType.LINK,
            "input": ElementType.INPUT,
            "textarea": ElementType.INPUT,
            "select": ElementType.INPUT,
            "img": ElementType.IMAGE,
            "form": ElementType.FORM,
            "h1": ElementType.HEADING,
            "h2": ElementType.HEADING,
            "h3": ElementType.HEADING,
            "h4": ElementType.HEADING,
            "h5": ElementType.HEADING,
            "h6": ElementType.HEADING,
            "ul": ElementType.LIST,
            "ol": ElementType.LIST,
            "table": ElementType.TABLE,
            "dialog": ElementType.DIALOG,
        }

        return tag_map.get(tag_name, ElementType.OTHER)

    async def click_by_ref(self, ref: str) -> bool:
        """Click an element by reference."""
        locator = self._element_map.get(ref)
        if not locator:
            return False

        try:
            await locator.click()
            return True
        except Exception:
            return False

    async def fill_by_ref(self, ref: str, value: str) -> bool:
        """Fill an input element by reference."""
        locator = self._element_map.get(ref)
        if not locator:
            return False

        try:
            await locator.fill(value)
            return True
        except Exception:
            return False

    async def get_element_by_ref(self, ref: str) -> ElementReference | None:
        """Get element information by reference."""
        if self._tree:
            return self._tree.get_element(ref)
        return None

    def get_tree(self) -> ElementTree | None:
        """Get the current element tree."""
        return self._tree

    def clear(self) -> None:
        """Clear all element references."""
        self._ref_counter = 0
        self._element_map.clear()
        self._tree = None
