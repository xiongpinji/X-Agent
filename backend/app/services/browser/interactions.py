"""
Advanced interaction capabilities for browser automation.

Implements drag & drop, file upload/download, keyboard shortcuts,
mouse hover, scroll to element, and iframe handling.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, List

logger = logging.getLogger(__name__)


class InteractionType(str, Enum):
    """Types of browser interactions."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    HOVER = "hover"
    DRAG = "drag"
    DROP = "drop"
    SCROLL = "scroll"
    TYPE = "type"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    KEYBOARD = "keyboard"


@dataclass
class InteractionResult:
    """Result of an interaction."""
    success: bool
    interaction_type: InteractionType
    time_taken_ms: float
    element_selector: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AdvancedInteractions:
    """
    Advanced browser interactions beyond basic click/fill.
    """

    def __init__(self, session_id: str):
        """
        Initialize advanced interactions.

        Args:
            session_id: Browser session ID
        """
        self.session_id = session_id
        self.logger = logger
        self.interaction_history: list[InteractionResult] = []

    async def drag_and_drop(
        self,
        page: Any,
        source_selector: str,
        target_selector: str,
    ) -> InteractionResult:
        """
        Drag element from source to target.

        Args:
            page: Playwright page object
            source_selector: Source element selector
            target_selector: Target element selector

        Returns:
            InteractionResult
        """
        import time
        start_time = time.time()

        try:
            source = page.locator(source_selector)
            target = page.locator(target_selector)

            # Scroll both elements into view
            await source.scroll_into_view_if_needed()
            await target.scroll_into_view_if_needed()

            # Get bounding boxes
            source_box = await source.bounding_box()
            target_box = await target.bounding_box()

            if not source_box or not target_box:
                raise ValueError("Could not get bounding boxes")

            # Calculate center points
            source_x = source_box["x"] + source_box["width"] / 2
            source_y = source_box["y"] + source_box["height"] / 2
            target_x = target_box["x"] + target_box["width"] / 2
            target_y = target_box["y"] + target_box["height"] / 2

            # Perform drag and drop
            await page.mouse.move(source_x, source_y)
            await page.mouse.down()
            await page.mouse.move(target_x, target_y, steps=10)
            await page.mouse.up()

            elapsed = (time.time() - start_time) * 1000
            result = InteractionResult(
                success=True,
                interaction_type=InteractionType.DRAG,
                time_taken_ms=elapsed,
                element_selector=source_selector,
                metadata={
                    "source": source_selector,
                    "target": target_selector,
                }
            )
            self._record_interaction(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.error(f"Drag and drop failed: {e}")
            result = InteractionResult(
                success=False,
                interaction_type=InteractionType.DRAG,
                time_taken_ms=elapsed,
                element_selector=source_selector,
                error=str(e),
            )
            self._record_interaction(result)
            return result

    async def upload_file(
        self,
        page: Any,
        file_input_selector: str,
        file_path: str,
    ) -> InteractionResult:
        """
        Upload file to file input element.

        Args:
            page: Playwright page object
            file_input_selector: File input element selector
            file_path: Path to file to upload

        Returns:
            InteractionResult
        """
        import time
        start_time = time.time()

        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_input = page.locator(file_input_selector)
            await file_input.set_input_files(file_path)

            elapsed = (time.time() - start_time) * 1000
            result = InteractionResult(
                success=True,
                interaction_type=InteractionType.UPLOAD,
                time_taken_ms=elapsed,
                element_selector=file_input_selector,
                metadata={
                    "file_path": file_path,
                    "file_size": os.path.getsize(file_path),
                }
            )
            self._record_interaction(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.error(f"File upload failed: {e}")
            result = InteractionResult(
                success=False,
                interaction_type=InteractionType.UPLOAD,
                time_taken_ms=elapsed,
                element_selector=file_input_selector,
                error=str(e),
            )
            self._record_interaction(result)
            return result

    async def hover_element(
        self,
        page: Any,
        selector: str,
        duration_ms: int = 500,
    ) -> InteractionResult:
        """
        Hover over element.

        Args:
            page: Playwright page object
            selector: Element selector
            duration_ms: Duration to hover in milliseconds

        Returns:
            InteractionResult
        """
        import time
        start_time = time.time()

        try:
            element = page.locator(selector)
            await element.scroll_into_view_if_needed()
            await element.hover()
            await asyncio.sleep(duration_ms / 1000.0)

            elapsed = (time.time() - start_time) * 1000
            result = InteractionResult(
                success=True,
                interaction_type=InteractionType.HOVER,
                time_taken_ms=elapsed,
                element_selector=selector,
                metadata={"duration_ms": duration_ms}
            )
            self._record_interaction(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.error(f"Hover failed: {e}")
            result = InteractionResult(
                success=False,
                interaction_type=InteractionType.HOVER,
                time_taken_ms=elapsed,
                element_selector=selector,
                error=str(e),
            )
            self._record_interaction(result)
            return result

    async def scroll_to_element(
        self,
        page: Any,
        selector: str,
        smooth: bool = True,
    ) -> InteractionResult:
        """
        Scroll to element.

        Args:
            page: Playwright page object
            selector: Element selector
            smooth: Use smooth scrolling

        Returns:
            InteractionResult
        """
        import time
        start_time = time.time()

        try:
            element = page.locator(selector)

            if smooth:
                await page.evaluate(
                    f"""
                    document.querySelector('{selector}').scrollIntoView({{
                        behavior: 'smooth',
                        block: 'center'
                    }});
                    """
                )
                await asyncio.sleep(0.5)
            else:
                await element.scroll_into_view_if_needed()

            elapsed = (time.time() - start_time) * 1000
            result = InteractionResult(
                success=True,
                interaction_type=InteractionType.SCROLL,
                time_taken_ms=elapsed,
                element_selector=selector,
                metadata={"smooth": smooth}
            )
            self._record_interaction(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.error(f"Scroll to element failed: {e}")
            result = InteractionResult(
                success=False,
                interaction_type=InteractionType.SCROLL,
                time_taken_ms=elapsed,
                element_selector=selector,
                error=str(e),
            )
            self._record_interaction(result)
            return result

    async def keyboard_shortcut(
        self,
        page: Any,
        keys: str,
    ) -> InteractionResult:
        """
        Press keyboard shortcut.

        Args:
            page: Playwright page object
            keys: Keys to press (e.g., "Control+A", "Meta+S")

        Returns:
            InteractionResult
        """
        import time
        start_time = time.time()

        try:
            await page.keyboard.press(keys)

            elapsed = (time.time() - start_time) * 1000
            result = InteractionResult(
                success=True,
                interaction_type=InteractionType.KEYBOARD,
                time_taken_ms=elapsed,
                metadata={"keys": keys}
            )
            self._record_interaction(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.error(f"Keyboard shortcut failed: {e}")
            result = InteractionResult(
                success=False,
                interaction_type=InteractionType.KEYBOARD,
                time_taken_ms=elapsed,
                error=str(e),
                metadata={"keys": keys}
            )
            self._record_interaction(result)
            return result

    async def type_text(
        self,
        page: Any,
        selector: str,
        text: str,
        delay_ms: int = 50,
        clear_first: bool = True,
    ) -> InteractionResult:
        """
        Type text into element with optional delay.

        Args:
            page: Playwright page object
            selector: Element selector
            text: Text to type
            delay_ms: Delay between keystrokes in milliseconds
            clear_first: Clear element before typing

        Returns:
            InteractionResult
        """
        import time
        start_time = time.time()

        try:
            element = page.locator(selector)
            await element.scroll_into_view_if_needed()

            if clear_first:
                await element.clear()

            await element.type(text, delay=delay_ms)

            elapsed = (time.time() - start_time) * 1000
            result = InteractionResult(
                success=True,
                interaction_type=InteractionType.TYPE,
                time_taken_ms=elapsed,
                element_selector=selector,
                metadata={
                    "text_length": len(text),
                    "delay_ms": delay_ms,
                }
            )
            self._record_interaction(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.error(f"Type text failed: {e}")
            result = InteractionResult(
                success=False,
                interaction_type=InteractionType.TYPE,
                time_taken_ms=elapsed,
                element_selector=selector,
                error=str(e),
            )
            self._record_interaction(result)
            return result

    async def double_click(
        self,
        page: Any,
        selector: str,
    ) -> InteractionResult:
        """
        Double click element.

        Args:
            page: Playwright page object
            selector: Element selector

        Returns:
            InteractionResult
        """
        import time
        start_time = time.time()

        try:
            element = page.locator(selector)
            await element.scroll_into_view_if_needed()
            await element.dblclick()

            elapsed = (time.time() - start_time) * 1000
            result = InteractionResult(
                success=True,
                interaction_type=InteractionType.DOUBLE_CLICK,
                time_taken_ms=elapsed,
                element_selector=selector,
            )
            self._record_interaction(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.error(f"Double click failed: {e}")
            result = InteractionResult(
                success=False,
                interaction_type=InteractionType.DOUBLE_CLICK,
                time_taken_ms=elapsed,
                element_selector=selector,
                error=str(e),
            )
            self._record_interaction(result)
            return result

    async def right_click(
        self,
        page: Any,
        selector: str,
    ) -> InteractionResult:
        """
        Right click element.

        Args:
            page: Playwright page object
            selector: Element selector

        Returns:
            InteractionResult
        """
        import time
        start_time = time.time()

        try:
            element = page.locator(selector)
            await element.scroll_into_view_if_needed()
            await element.click(button="right")

            elapsed = (time.time() - start_time) * 1000
            result = InteractionResult(
                success=True,
                interaction_type=InteractionType.RIGHT_CLICK,
                time_taken_ms=elapsed,
                element_selector=selector,
            )
            self._record_interaction(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.error(f"Right click failed: {e}")
            result = InteractionResult(
                success=False,
                interaction_type=InteractionType.RIGHT_CLICK,
                time_taken_ms=elapsed,
                element_selector=selector,
                error=str(e),
            )
            self._record_interaction(result)
            return result

    async def handle_iframe(
        self,
        page: Any,
        iframe_selector: str,
    ) -> Optional[Any]:
        """
        Get iframe page object for interaction.

        Args:
            page: Playwright page object
            iframe_selector: Iframe selector

        Returns:
            Iframe page object or None
        """
        try:
            frame_locator = page.frame_locator(iframe_selector)
            return frame_locator
        except Exception as e:
            self.logger.error(f"Failed to handle iframe: {e}")
            return None

    def _record_interaction(self, result: InteractionResult) -> None:
        """Record interaction for analytics."""
        self.interaction_history.append(result)
        self.logger.debug(
            f"Interaction recorded: {result.interaction_type.value}, "
            f"time: {result.time_taken_ms:.2f}ms, "
            f"success: {result.success}"
        )

    def get_interaction_stats(self) -> dict:
        """Get interaction statistics."""
        successful = sum(1 for i in self.interaction_history if i.success)
        failed = len(self.interaction_history) - successful

        by_type = {}
        for interaction in self.interaction_history:
            itype = interaction.interaction_type.value
            if itype not in by_type:
                by_type[itype] = {"count": 0, "success": 0}
            by_type[itype]["count"] += 1
            if interaction.success:
                by_type[itype]["success"] += 1

        return {
            "total_interactions": len(self.interaction_history),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(self.interaction_history) if self.interaction_history else 0,
            "by_type": by_type,
        }

    def clear_history(self) -> None:
        """Clear interaction history."""
        self.interaction_history.clear()


def create_advanced_interactions(session_id: str) -> AdvancedInteractions:
    """Create advanced interactions for a session."""
    return AdvancedInteractions(session_id)
