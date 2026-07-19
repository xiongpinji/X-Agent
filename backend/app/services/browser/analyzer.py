# 未接线（P0-11 审计标注）：本模块为宣传的企业级浏览器增强能力，但当前没有任何 API 消费方，未暴露到任何接口。按要求保留代码，待后续接线或归档。
"""
Page analysis and structure extraction for browser automation.

Analyzes page structure, identifies forms, buttons, links, and extracts data.
"""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Any, List, Dict

logger = logging.getLogger(__name__)


class ElementType(str, Enum):
    """Types of page elements."""
    BUTTON = "button"
    LINK = "link"
    INPUT = "input"
    FORM = "form"
    TABLE = "table"
    IMAGE = "image"
    TEXT = "text"
    HEADING = "heading"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    RADIO = "radio"


@dataclass
class PageElement:
    """Represents a page element."""
    element_type: ElementType
    selector: str
    text: Optional[str] = None
    tag: Optional[str] = None
    attributes: Dict[str, str] = None
    visible: bool = True
    clickable: bool = False
    bounding_box: Optional[Dict[str, float]] = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


@dataclass
class FormInfo:
    """Information about a form."""
    selector: str
    method: Optional[str] = None
    action: Optional[str] = None
    fields: List[PageElement] = None
    submit_button: Optional[PageElement] = None

    def __post_init__(self):
        if self.fields is None:
            self.fields = []


@dataclass
class PageStructure:
    """Complete page structure analysis."""
    url: str
    title: str
    buttons: List[PageElement]
    links: List[PageElement]
    forms: List[FormInfo]
    inputs: List[PageElement]
    headings: List[PageElement]
    tables: List[PageElement]
    images: List[PageElement]
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PageAnalyzer:
    """
    Analyzes page structure and extracts information.
    """

    def __init__(self, session_id: str):
        """
        Initialize page analyzer.

        Args:
            session_id: Browser session ID
        """
        self.session_id = session_id
        self.logger = logger

    async def analyze_page(self, page: Any) -> PageStructure:
        """
        Analyze complete page structure.

        Args:
            page: Playwright page object

        Returns:
            PageStructure with all elements
        """
        try:
            url = page.url
            title = await page.title()

            # Extract all element types
            buttons = await self._extract_buttons(page)
            links = await self._extract_links(page)
            forms = await self._extract_forms(page)
            inputs = await self._extract_inputs(page)
            headings = await self._extract_headings(page)
            tables = await self._extract_tables(page)
            images = await self._extract_images(page)

            structure = PageStructure(
                url=url,
                title=title,
                buttons=buttons,
                links=links,
                forms=forms,
                inputs=inputs,
                headings=headings,
                tables=tables,
                images=images,
                metadata={
                    "element_count": len(buttons) + len(links) + len(inputs),
                    "form_count": len(forms),
                }
            )

            self.logger.info(f"Page analysis complete: {len(buttons)} buttons, "
                           f"{len(links)} links, {len(forms)} forms")
            return structure

        except Exception as e:
            self.logger.error(f"Page analysis failed: {e}")
            raise

    async def _extract_buttons(self, page: Any) -> List[PageElement]:
        """Extract all buttons from page."""
        try:
            buttons = []
            button_locators = page.locator("button, input[type='button'], input[type='submit']")
            count = await button_locators.count()

            for i in range(count):
                try:
                    locator = button_locators.nth(i)
                    text = await locator.text_content()
                    selector = await self._get_selector(page, locator)
                    visible = await locator.is_visible()
                    clickable = await locator.is_enabled()

                    button = PageElement(
                        element_type=ElementType.BUTTON,
                        selector=selector,
                        text=text.strip() if text else None,
                        visible=visible,
                        clickable=clickable,
                    )
                    buttons.append(button)
                except Exception as e:
                    self.logger.debug(f"Failed to extract button: {e}")

            return buttons
        except Exception as e:
            self.logger.error(f"Button extraction failed: {e}")
            return []

    async def _extract_links(self, page: Any) -> List[PageElement]:
        """Extract all links from page."""
        try:
            links = []
            link_locators = page.locator("a")
            count = await link_locators.count()

            for i in range(count):
                try:
                    locator = link_locators.nth(i)
                    text = await locator.text_content()
                    href = await locator.get_attribute("href")
                    selector = await self._get_selector(page, locator)
                    visible = await locator.is_visible()

                    link = PageElement(
                        element_type=ElementType.LINK,
                        selector=selector,
                        text=text.strip() if text else None,
                        visible=visible,
                        attributes={"href": href} if href else {},
                    )
                    links.append(link)
                except Exception as e:
                    self.logger.debug(f"Failed to extract link: {e}")

            return links
        except Exception as e:
            self.logger.error(f"Link extraction failed: {e}")
            return []

    async def _extract_forms(self, page: Any) -> List[FormInfo]:
        """Extract all forms from page."""
        try:
            forms = []
            form_locators = page.locator("form")
            count = await form_locators.count()

            for i in range(count):
                try:
                    locator = form_locators.nth(i)
                    selector = await self._get_selector(page, locator)
                    method = await locator.get_attribute("method")
                    action = await locator.get_attribute("action")

                    # Extract form fields
                    fields = await self._extract_form_fields(page, selector)

                    # Find submit button
                    submit_button = None
                    submit_locators = locator.locator("button[type='submit'], input[type='submit']")
                    if await submit_locators.count() > 0:
                        submit_text = await submit_locators.first.text_content()
                        submit_selector = await self._get_selector(page, submit_locators.first)
                        submit_button = PageElement(
                            element_type=ElementType.BUTTON,
                            selector=submit_selector,
                            text=submit_text.strip() if submit_text else "Submit",
                        )

                    form = FormInfo(
                        selector=selector,
                        method=method,
                        action=action,
                        fields=fields,
                        submit_button=submit_button,
                    )
                    forms.append(form)
                except Exception as e:
                    self.logger.debug(f"Failed to extract form: {e}")

            return forms
        except Exception as e:
            self.logger.error(f"Form extraction failed: {e}")
            return []

    async def _extract_form_fields(self, page: Any, form_selector: str) -> List[PageElement]:
        """Extract fields from a form."""
        try:
            fields = []
            form = page.locator(form_selector)

            # Extract input fields
            inputs = form.locator("input, textarea, select")
            count = await inputs.count()

            for i in range(count):
                try:
                    locator = inputs.nth(i)
                    tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                    name = await locator.get_attribute("name")
                    input_type = await locator.get_attribute("type")
                    selector = await self._get_selector(page, locator)

                    field = PageElement(
                        element_type=ElementType.INPUT,
                        selector=selector,
                        tag=tag,
                        attributes={
                            "name": name,
                            "type": input_type,
                        }
                    )
                    fields.append(field)
                except Exception as e:
                    self.logger.debug(f"Failed to extract form field: {e}")

            return fields
        except Exception as e:
            self.logger.error(f"Form field extraction failed: {e}")
            return []

    async def _extract_inputs(self, page: Any) -> List[PageElement]:
        """Extract all input elements from page."""
        try:
            inputs = []
            input_locators = page.locator("input, textarea, select")
            count = await input_locators.count()

            for i in range(count):
                try:
                    locator = input_locators.nth(i)
                    tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                    name = await locator.get_attribute("name")
                    input_type = await locator.get_attribute("type")
                    selector = await self._get_selector(page, locator)
                    visible = await locator.is_visible()

                    input_elem = PageElement(
                        element_type=ElementType.INPUT,
                        selector=selector,
                        tag=tag,
                        visible=visible,
                        attributes={
                            "name": name,
                            "type": input_type,
                        }
                    )
                    inputs.append(input_elem)
                except Exception as e:
                    self.logger.debug(f"Failed to extract input: {e}")

            return inputs
        except Exception as e:
            self.logger.error(f"Input extraction failed: {e}")
            return []

    async def _extract_headings(self, page: Any) -> List[PageElement]:
        """Extract all headings from page."""
        try:
            headings = []
            heading_locators = page.locator("h1, h2, h3, h4, h5, h6")
            count = await heading_locators.count()

            for i in range(count):
                try:
                    locator = heading_locators.nth(i)
                    text = await locator.text_content()
                    tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                    selector = await self._get_selector(page, locator)

                    heading = PageElement(
                        element_type=ElementType.HEADING,
                        selector=selector,
                        text=text.strip() if text else None,
                        tag=tag,
                    )
                    headings.append(heading)
                except Exception as e:
                    self.logger.debug(f"Failed to extract heading: {e}")

            return headings
        except Exception as e:
            self.logger.error(f"Heading extraction failed: {e}")
            return []

    async def _extract_tables(self, page: Any) -> List[PageElement]:
        """Extract all tables from page."""
        try:
            tables = []
            table_locators = page.locator("table")
            count = await table_locators.count()

            for i in range(count):
                try:
                    locator = table_locators.nth(i)
                    selector = await self._get_selector(page, locator)

                    # Count rows and columns
                    rows = await locator.locator("tr").count()
                    cols = 0
                    if rows > 0:
                        cols = await locator.locator("tr").first.locator("td, th").count()

                    table = PageElement(
                        element_type=ElementType.TABLE,
                        selector=selector,
                        attributes={
                            "rows": str(rows),
                            "columns": str(cols),
                        }
                    )
                    tables.append(table)
                except Exception as e:
                    self.logger.debug(f"Failed to extract table: {e}")

            return tables
        except Exception as e:
            self.logger.error(f"Table extraction failed: {e}")
            return []

    async def _extract_images(self, page: Any) -> List[PageElement]:
        """Extract all images from page."""
        try:
            images = []
            image_locators = page.locator("img")
            count = await image_locators.count()

            for i in range(count):
                try:
                    locator = image_locators.nth(i)
                    src = await locator.get_attribute("src")
                    alt = await locator.get_attribute("alt")
                    selector = await self._get_selector(page, locator)
                    visible = await locator.is_visible()

                    image = PageElement(
                        element_type=ElementType.IMAGE,
                        selector=selector,
                        text=alt,
                        visible=visible,
                        attributes={"src": src} if src else {},
                    )
                    images.append(image)
                except Exception as e:
                    self.logger.debug(f"Failed to extract image: {e}")

            return images
        except Exception as e:
            self.logger.error(f"Image extraction failed: {e}")
            return []

    async def _get_selector(self, page: Any, locator: Any) -> str:
        """Get CSS selector for element."""
        try:
            selector = await page.evaluate(
                """(element) => {
                    if (element.id) return '#' + element.id;
                    if (element.className) return '.' + element.className.split(' ').join('.');
                    return element.tagName.toLowerCase();
                }""",
                await locator.element_handle()
            )
            return selector
        except Exception:
            return "unknown"

    async def extract_text_content(self, page: Any, selector: str) -> str:
        """Extract text content from element."""
        try:
            text = await page.locator(selector).text_content()
            return text.strip() if text else ""
        except Exception as e:
            self.logger.error(f"Text extraction failed: {e}")
            return ""

    async def extract_table_data(self, page: Any, selector: str) -> List[Dict[str, str]]:
        """Extract data from table."""
        try:
            data = []
            table = page.locator(selector)

            # Get headers
            headers = []
            header_cells = table.locator("thead th, tr:first-child th")
            header_count = await header_cells.count()

            for i in range(header_count):
                text = await header_cells.nth(i).text_content()
                headers.append(text.strip() if text else f"col_{i}")

            # Get rows
            rows = table.locator("tbody tr, tr:not(:first-child)")
            row_count = await rows.count()

            for i in range(row_count):
                row_data = {}
                cells = rows.nth(i).locator("td")
                cell_count = await cells.count()

                for j in range(cell_count):
                    text = await cells.nth(j).text_content()
                    header = headers[j] if j < len(headers) else f"col_{j}"
                    row_data[header] = text.strip() if text else ""

                data.append(row_data)

            return data
        except Exception as e:
            self.logger.error(f"Table data extraction failed: {e}")
            return []


def create_page_analyzer(session_id: str) -> PageAnalyzer:
    """Create a page analyzer for a session."""
    return PageAnalyzer(session_id)
