"""Computer Use — Hermes-Agent style desktop control (cua-driver pattern).

This module implements screenshot-driven desktop automation:

* :class:`ComputerUseAgent` — low-level mouse/keyboard/screen primitives that
  work cross-platform (Windows/macOS via ``pyautogui``, Linux via ``xdotool``).
* :class:`ScreenAnalyzer` — LLM-vision layer that understands screenshots,
  locates UI elements and verifies that actions succeeded.
* :class:`ActionPlan` — turns a high-level task into a sequence of low-level
  actions, executing each step with verification and auto-retry.
* :class:`ComputerUseSession` — session wrapper that records every action for
  replay/audit, enforces safety (allowed/blocked applications, confirmation for
  destructive actions) and rate limiting (max 10 actions/second).

All platform-specific imports are optional and guarded by ``try/except`` so the
module degrades gracefully: when no GUI backend is available the agent runs in
``dry_run`` mode (actions are validated and recorded but not physically
performed) instead of crashing at import time.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
import subprocess
import sys
import time
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Optional platform imports (graceful degradation)
# --------------------------------------------------------------------------- #
try:  # pyautogui covers Windows + macOS (and Linux with X)
    import pyautogui  # type: ignore

    _PYAUTOGUI_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    pyautogui = None  # type: ignore[assignment]
    _PYAUTOGUI_AVAILABLE = False

try:  # Pillow is used to encode screenshots to PNG bytes
    from PIL import Image  # type: ignore

    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    Image = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False


IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class ComputerUseError(RuntimeError):
    """Base error for computer-use failures."""


class BackendUnavailableError(ComputerUseError):
    """Raised when no GUI automation backend is available and not in dry-run."""


class ConfirmationRequiredError(ComputerUseError):
    """Raised when a destructive action needs explicit user confirmation."""

    def __init__(self, action: str, reason: str) -> None:
        super().__init__(f"Confirmation required for '{action}': {reason}")
        self.action = action
        self.reason = reason


class RateLimitExceededError(ComputerUseError):
    """Raised when the action rate limit is exceeded."""


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class BoundingBox:
    """Axis-aligned rectangle describing a UI element location (pixels)."""

    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    label: str = ""

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center_x": self.center[0],
            "center_y": self.center[1],
            "confidence": self.confidence,
            "label": self.label,
        }


# --------------------------------------------------------------------------- #
# Rate limiter (max N actions per second, sliding window)
# --------------------------------------------------------------------------- #
class RateLimiter:
    """Simple sliding-window rate limiter.

    Defaults to 10 actions/second per the computer-use safety requirements.
    """

    def __init__(self, max_per_second: int = 10) -> None:
        self.max_per_second = max(1, int(max_per_second))
        self._events: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until an action slot is available (never drops actions)."""
        async with self._lock:
            while True:
                now = time.monotonic()
                while self._events and now - self._events[0] >= 1.0:
                    self._events.popleft()
                if len(self._events) < self.max_per_second:
                    self._events.append(now)
                    return
                # Wait until the oldest event leaves the 1s window.
                wait_for = 1.0 - (now - self._events[0])
                await asyncio.sleep(max(wait_for, 0.001))

    def try_acquire(self) -> bool:
        """Non-blocking variant: return False instead of waiting."""
        now = time.monotonic()
        while self._events and now - self._events[0] >= 1.0:
            self._events.popleft()
        if len(self._events) < self.max_per_second:
            self._events.append(now)
            return True
        return False


# --------------------------------------------------------------------------- #
# Platform drivers
# --------------------------------------------------------------------------- #
class PlatformDriver:
    """Abstract low-level GUI driver interface."""

    name = "base"
    available = False

    def screen_size(self) -> tuple[int, int]:
        raise BackendUnavailableError(f"{self.name} driver cannot report screen size")

    def screenshot(self) -> bytes:
        raise BackendUnavailableError(f"{self.name} driver cannot capture screenshots")

    def click(self, x: int, y: int, button: str = "left") -> None:
        raise BackendUnavailableError(f"{self.name} driver cannot click")

    def double_click(self, x: int, y: int) -> None:
        raise BackendUnavailableError(f"{self.name} driver cannot double click")

    def move_to(self, x: int, y: int) -> None:
        raise BackendUnavailableError(f"{self.name} driver cannot move the mouse")

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        raise BackendUnavailableError(f"{self.name} driver cannot drag")

    def type_text(self, text: str) -> None:
        raise BackendUnavailableError(f"{self.name} driver cannot type text")

    def press_key(self, key: str) -> None:
        raise BackendUnavailableError(f"{self.name} driver cannot press keys")

    def hotkey(self, *keys: str) -> None:
        raise BackendUnavailableError(f"{self.name} driver cannot send hotkeys")

    def scroll(self, direction: str, amount: int) -> None:
        raise BackendUnavailableError(f"{self.name} driver cannot scroll")


class PyAutoGuiDriver(PlatformDriver):
    """Cross-platform driver backed by ``pyautogui`` (Windows/macOS/Linux-X)."""

    name = "pyautogui"
    available = _PYAUTOGUI_AVAILABLE

    def __init__(self) -> None:
        if not _PYAUTOGUI_AVAILABLE:
            raise BackendUnavailableError("pyautogui is not installed")
        # Disable the fail-safe move-to-corner abort for programmatic control,
        # but keep a small pause so rapid actions remain observable.
        try:
            pyautogui.FAILSAFE = False
            pyautogui.PAUSE = 0.02
        except Exception:  # pragma: no cover - defensive
            pass

    def screen_size(self) -> tuple[int, int]:
        width, height = pyautogui.size()
        return int(width), int(height)

    def screenshot(self) -> bytes:
        image = pyautogui.screenshot()
        return _image_to_png_bytes(image)

    def click(self, x: int, y: int, button: str = "left") -> None:
        pyautogui.click(x=int(x), y=int(y), button=button)

    def double_click(self, x: int, y: int) -> None:
        pyautogui.doubleClick(x=int(x), y=int(y))

    def move_to(self, x: int, y: int) -> None:
        pyautogui.moveTo(x=int(x), y=int(y))

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        pyautogui.moveTo(x=int(start_x), y=int(start_y))
        pyautogui.dragTo(x=int(end_x), y=int(end_y), duration=0.2)

    def type_text(self, text: str) -> None:
        # write() only supports ASCII; fall back to pyperclip-style paste for
        # unicode by typing character-by-character via typewrite is unreliable,
        # so use write() for the common case.
        pyautogui.write(text, interval=0.01)

    def press_key(self, key: str) -> None:
        pyautogui.press(key)

    def hotkey(self, *keys: str) -> None:
        pyautogui.hotkey(*keys)

    def scroll(self, direction: str, amount: int) -> None:
        clicks = int(amount)
        if direction == "down":
            clicks = -clicks
        pyautogui.scroll(clicks)


class XdotoolDriver(PlatformDriver):
    """Linux driver backed by the ``xdotool`` CLI (no Python deps required)."""

    name = "xdotool"

    def __init__(self) -> None:
        self.available = self._probe()

    @staticmethod
    def _probe() -> bool:
        if not IS_LINUX:
            return False
        try:
            result = subprocess.run(
                ["xdotool", "version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["xdotool", *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            raise ComputerUseError(f"xdotool failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def screen_size(self) -> tuple[int, int]:
        output = self._run("getdisplaygeometry")
        width, _, height = output.partition(" ")
        return int(width), int(height)

    def screenshot(self) -> bytes:
        # Prefer scrot / gnome-screenshot / import (ImageMagick) when present.
        for _tool, builder in (
            ("scrot", lambda path: ["scrot", "-o", path]),
            ("import", lambda path: ["import", "-window", "root", path]),
        ):
            try:
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    path = tmp.name
                subprocess.run(builder(path), capture_output=True, timeout=15, check=True)
                with open(path, "rb") as handle:
                    return handle.read()
            except Exception:
                continue
        raise BackendUnavailableError("No Linux screenshot tool available (scrot/import)")

    def click(self, x: int, y: int, button: str = "left") -> None:
        button_map = {"left": "1", "middle": "2", "right": "3"}
        self.move_to(x, y)
        self._run("click", button_map.get(button, "1"))

    def double_click(self, x: int, y: int) -> None:
        self.move_to(x, y)
        self._run("click", "--repeat", "2", "--delay", "80", "1")

    def move_to(self, x: int, y: int) -> None:
        self._run("mousemove", str(int(x)), str(int(y)))

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        self._run("mousemove", str(int(start_x)), str(int(start_y)))
        self._run("mousedown", "1")
        self._run("mousemove", "--sync", str(int(end_x)), str(int(end_y)))
        self._run("mouseup", "1")

    def type_text(self, text: str) -> None:
        self._run("type", "--clearmodifiers", text)

    def press_key(self, key: str) -> None:
        self._run("key", _normalize_key_for_xdotool(key))

    def hotkey(self, *keys: str) -> None:
        combo = "+".join(_normalize_key_for_xdotool(k) for k in keys)
        self._run("key", combo)

    def scroll(self, direction: str, amount: int) -> None:
        button = "5" if direction == "down" else "4"
        for _ in range(int(amount)):
            self._run("click", button)


class DryRunDriver(PlatformDriver):
    """No-op driver used when no GUI backend exists or for testing.

    Produces a deterministic blank PNG screenshot so downstream vision code has
    something to work with, and records every primitive for inspection.
    """

    name = "dry-run"
    available = True

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self._width = width
        self._height = height
        self.calls: list[dict[str, Any]] = []

    def _record(self, op: str, **kwargs: Any) -> None:
        self.calls.append({"op": op, **kwargs})

    def screen_size(self) -> tuple[int, int]:
        return self._width, self._height

    def screenshot(self) -> bytes:
        self._record("screenshot")
        return _blank_png_bytes(self._width, self._height)

    def click(self, x: int, y: int, button: str = "left") -> None:
        self._record("click", x=x, y=y, button=button)

    def double_click(self, x: int, y: int) -> None:
        self._record("double_click", x=x, y=y)

    def move_to(self, x: int, y: int) -> None:
        self._record("move_to", x=x, y=y)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        self._record("drag", start_x=start_x, start_y=start_y, end_x=end_x, end_y=end_y)

    def type_text(self, text: str) -> None:
        self._record("type_text", text=text)

    def press_key(self, key: str) -> None:
        self._record("press_key", key=key)

    def hotkey(self, *keys: str) -> None:
        self._record("hotkey", keys=list(keys))

    def scroll(self, direction: str, amount: int) -> None:
        self._record("scroll", direction=direction, amount=amount)


def get_platform_driver(*, force_dry_run: bool = False) -> PlatformDriver:
    """Factory: pick the best available driver for the current platform."""
    if force_dry_run:
        return DryRunDriver()
    if IS_LINUX and not _PYAUTOGUI_AVAILABLE:
        driver = XdotoolDriver()
        if driver.available:
            return driver
    if _PYAUTOGUI_AVAILABLE:
        try:
            return PyAutoGuiDriver()
        except Exception as exc:  # pragma: no cover - environment specific
            logger.warning("pyautogui driver failed to initialize: %s", exc)
    if IS_LINUX:
        driver = XdotoolDriver()
        if driver.available:
            return driver
    logger.info("No GUI backend available; falling back to dry-run driver")
    return DryRunDriver()


# --------------------------------------------------------------------------- #
# Screenshot helpers
# --------------------------------------------------------------------------- #
def _image_to_png_bytes(image: Any) -> bytes:
    """Encode a PIL-like image object to PNG bytes."""
    if _PIL_AVAILABLE:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    # Some backends expose raw bytes directly.
    raw = getattr(image, "tobytes", None)
    if callable(raw):
        return raw()
    raise BackendUnavailableError("Pillow is required to encode screenshots")


def _blank_png_bytes(width: int, height: int) -> bytes:
    """Return a solid black PNG (used by the dry-run driver)."""
    if _PIL_AVAILABLE:
        buffer = io.BytesIO()
        Image.new("RGB", (width, height), (0, 0, 0)).save(buffer, format="PNG")
        return buffer.getvalue()
    # Minimal 1x1 black PNG when Pillow is unavailable.
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )


def _normalize_key_for_xdotool(key: str) -> str:
    """Map common key names to xdotool X keysym names."""
    mapping = {
        "enter": "Return",
        "return": "Return",
        "tab": "Tab",
        "escape": "Escape",
        "esc": "Escape",
        "backspace": "BackSpace",
        "delete": "Delete",
        "space": "space",
        "ctrl": "ctrl",
        "control": "ctrl",
        "alt": "alt",
        "shift": "shift",
        "super": "super",
        "cmd": "super",
        "command": "super",
        "win": "super",
        "up": "Up",
        "down": "Down",
        "left": "Left",
        "right": "Right",
    }
    return mapping.get(key.lower(), key)


# --------------------------------------------------------------------------- #
# LLM vision integration
# --------------------------------------------------------------------------- #
VisionFn = Callable[[bytes, str], Coroutine[Any, Any, str]]


def _extract_json(text: str) -> Any:
    """Best-effort extraction of a JSON object/array from LLM output."""
    if not text:
        return None
    # Strip markdown code fences.
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else text.strip()
    try:
        return json.loads(candidate)
    except (ValueError, TypeError):
        pass
    # Fall back to the first balanced {...} or [...] block.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except (ValueError, TypeError):
                continue
    return None


class ScreenAnalyzer:
    """Uses LLM vision (GPT-4o / Claude) to understand screenshots.

    The actual vision call is pluggable via ``vision_fn`` (async callable taking
    ``(screenshot_bytes, prompt) -> str``). When omitted, the shared
    ``LLMRouter`` is used and the screenshot is embedded as a base64 data URL in
    the prompt so any vision-capable backend can consume it.
    """

    def __init__(
        self,
        *,
        llm_router: Any | None = None,
        vision_fn: VisionFn | None = None,
        model_hint: str = "gpt-4o",
    ) -> None:
        self._llm_router = llm_router
        self._vision_fn = vision_fn
        self._model_hint = model_hint

    async def _ask_vision(self, screenshot: bytes, prompt: str) -> str:
        if self._vision_fn is not None:
            return await self._vision_fn(screenshot, prompt)
        return await self._ask_router(screenshot, prompt)

    async def _ask_router(self, screenshot: bytes, prompt: str) -> str:
        router = self._llm_router
        if router is None:
            try:
                from backend.app.dependencies import get_llm_router

                router = get_llm_router()
            except Exception as exc:  # pragma: no cover - wiring guard
                raise ComputerUseError(f"LLM router unavailable: {exc}") from exc
        encoded = base64.b64encode(screenshot).decode("ascii")
        content = (
            f"{prompt}\n\n"
            f"[Screenshot attached as base64 PNG data URL]\n"
            f"data:image/png;base64,{encoded}"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a precise computer-use vision assistant. Analyze the "
                    "attached screenshot and answer strictly in the requested format."
                ),
            },
            {"role": "user", "content": content},
        ]
        response = await router.chat(messages, [])
        return getattr(response, "content", "") or ""

    async def describe_screen(self, screenshot: bytes) -> str:
        """Return a natural-language description of what is currently visible."""
        prompt = (
            "Describe what is currently visible on this screen in 2-4 concise "
            "sentences: the active application, major UI regions, and any "
            "prominent dialogs or messages."
        )
        return (await self._ask_vision(screenshot, prompt)).strip()

    async def find_element(self, screenshot: bytes, description: str) -> BoundingBox:
        """Locate a UI element by natural-language description."""
        prompt = (
            "Locate the following UI element in the screenshot:\n"
            f'"{description}"\n\n'
            "Respond with ONLY a JSON object of the pixel bounding box:\n"
            '{"x": <int>, "y": <int>, "width": <int>, "height": <int>, '
            '"confidence": <float 0-1>, "label": "<short label>"}\n'
            "If the element is not present, set confidence to 0."
        )
        raw = await self._ask_vision(screenshot, prompt)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            raise ComputerUseError(f"Vision model returned unparsable element data: {raw[:200]}")
        box = BoundingBox(
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            confidence=float(data.get("confidence", 0.0)),
            label=str(data.get("label", description)),
        )
        if box.confidence <= 0 or box.width <= 0 or box.height <= 0:
            raise ComputerUseError(f"Element not found on screen: {description}")
        return box

    async def verify_action(self, expected: str, screenshot: bytes) -> bool:
        """Verify that an action produced the expected on-screen result."""
        prompt = (
            "Look at the screenshot and decide whether the following expected "
            "outcome is true.\n"
            f'Expected outcome: "{expected}"\n\n'
            "Respond with ONLY a JSON object: "
            '{"success": <true|false>, "reason": "<short explanation>"}'
        )
        raw = await self._ask_vision(screenshot, prompt)
        data = _extract_json(raw)
        if isinstance(data, dict) and "success" in data:
            return bool(data["success"])
        # Fallback heuristic for free-form answers.
        return raw.strip().lower().startswith(("true", "yes"))


# --------------------------------------------------------------------------- #
# Low-level agent
# --------------------------------------------------------------------------- #
class ComputerUseAgent:
    """Low-level, cross-platform desktop control primitives.

    Wraps a :class:`PlatformDriver` and adds LLM-vision powered element finding
    and condition waiting. All primitives are synchronous driver calls; the
    vision helpers are async.
    """

    def __init__(
        self,
        *,
        driver: PlatformDriver | None = None,
        analyzer: ScreenAnalyzer | None = None,
        dry_run: bool = False,
    ) -> None:
        self._driver = driver or get_platform_driver(force_dry_run=dry_run)
        self.analyzer = analyzer or ScreenAnalyzer()
        self.dry_run = isinstance(self._driver, DryRunDriver)

    @property
    def driver(self) -> PlatformDriver:
        return self._driver

    @property
    def backend_name(self) -> str:
        return self._driver.name

    def screen_size(self) -> tuple[int, int]:
        return self._driver.screen_size()

    def screenshot(self) -> bytes:
        """Capture the current screen as PNG bytes."""
        return self._driver.screenshot()

    def _validate_point(self, x: int, y: int) -> None:
        if x < 0 or y < 0:
            raise ValueError(f"Coordinates must be non-negative, got ({x}, {y})")
        try:
            width, height = self._driver.screen_size()
        except ComputerUseError:
            return
        if x > width or y > height:
            raise ValueError(
                f"Coordinates ({x}, {y}) outside screen bounds ({width}x{height})"
            )

    def click(self, x: int, y: int, button: str = "left") -> None:
        if button not in {"left", "right", "middle"}:
            raise ValueError(f"Invalid mouse button: {button}")
        self._validate_point(x, y)
        self._driver.click(x, y, button)

    def double_click(self, x: int, y: int) -> None:
        self._validate_point(x, y)
        self._driver.double_click(x, y)

    def right_click(self, x: int, y: int) -> None:
        self._validate_point(x, y)
        self._driver.click(x, y, "right")

    def move_to(self, x: int, y: int) -> None:
        self._validate_point(x, y)
        self._driver.move_to(x, y)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        self._validate_point(start_x, start_y)
        self._validate_point(end_x, end_y)
        self._driver.drag(start_x, start_y, end_x, end_y)

    def type_text(self, text: str) -> None:
        self._driver.type_text(text)

    def press_key(self, key: str) -> None:
        if not key:
            raise ValueError("key must be a non-empty string")
        self._driver.press_key(key)

    def hotkey(self, *keys: str) -> None:
        if not keys:
            raise ValueError("hotkey requires at least one key")
        self._driver.hotkey(*keys)

    def scroll(self, direction: str, amount: int = 3) -> None:
        if direction not in {"up", "down"}:
            raise ValueError("direction must be 'up' or 'down'")
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._driver.scroll(direction, amount)

    async def find_on_screen(self, description: str) -> tuple[int, int]:
        """Use LLM vision to locate an element and return its center coords."""
        image = self.screenshot()
        box = await self.analyzer.find_element(image, description)
        return box.center

    async def wait_for(
        self,
        condition: str,
        timeout: float = 30.0,
        poll_interval: float = 1.0,
    ) -> bool:
        """Poll the screen until the LLM confirms ``condition`` or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            image = self.screenshot()
            if await self.analyzer.verify_action(condition, image):
                return True
            await asyncio.sleep(poll_interval)
        return False


# --------------------------------------------------------------------------- #
# Action planning
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class PlannedStep:
    """A single low-level action produced by the planner."""

    action: str
    params: dict[str, Any] = field(default_factory=dict)
    expect: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "params": self.params,
            "expect": self.expect,
            "description": self.description,
        }


@dataclass(slots=True)
class StepResult:
    step: PlannedStep
    ok: bool
    attempts: int = 1
    detail: str = ""
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step.to_dict(),
            "ok": self.ok,
            "attempts": self.attempts,
            "detail": self.detail,
            "verified": self.verified,
        }


class ActionPlan:
    """Turns a high-level task into low-level actions and executes them.

    The planner asks an LLM to emit a JSON array of steps given the task and a
    screenshot. Execution runs each step through a :class:`ComputerUseAgent`,
    verifies the expected outcome with vision, and auto-retries with adjusted
    coordinates on failure.
    """

    def __init__(
        self,
        agent: ComputerUseAgent,
        *,
        llm_router: Any | None = None,
        plan_fn: Callable[[str, bytes], Coroutine[Any, Any, str]] | None = None,
        max_retries: int = 2,
    ) -> None:
        self.agent = agent
        self._llm_router = llm_router
        self._plan_fn = plan_fn
        self.max_retries = max_retries

    async def plan(self, task: str, screenshot: bytes | None = None) -> list[PlannedStep]:
        """Generate a sequence of low-level steps for a high-level task."""
        image = screenshot if screenshot is not None else self.agent.screenshot()
        if self._plan_fn is not None:
            raw = await self._plan_fn(task, image)
        else:
            raw = await self._plan_via_router(task, image)
        data = _extract_json(raw)
        if isinstance(data, dict) and "steps" in data:
            data = data["steps"]
        if not isinstance(data, list):
            raise ComputerUseError(f"Planner returned unparsable plan: {raw[:200]}")
        steps: list[PlannedStep] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            steps.append(
                PlannedStep(
                    action=str(item.get("action", "")),
                    params=dict(item.get("params", {}) or {}),
                    expect=str(item.get("expect", "")),
                    description=str(item.get("description", "")),
                )
            )
        if not steps:
            raise ComputerUseError("Planner produced an empty action plan")
        return steps

    async def _plan_via_router(self, task: str, screenshot: bytes) -> str:
        router = self._llm_router
        if router is None:
            from backend.app.dependencies import get_llm_router

            router = get_llm_router()
        encoded = base64.b64encode(screenshot).decode("ascii")
        prompt = (
            "You are planning desktop automation. Given the task and the current "
            "screenshot, output ONLY a JSON array of steps. Each step:\n"
            '{"action": "<click|double_click|right_click|type_text|press_key|'
            'hotkey|scroll|drag|move_to|wait>", '
            '"params": {<action-specific>}, "expect": "<visible outcome>", '
            '"description": "<human readable>"}\n'
            "For click/double_click/right_click/move_to params use "
            '{"x": int, "y": int}. For type_text {"text": str}. For press_key '
            '{"key": str}. For hotkey {"keys": [str]}. For scroll '
            '{"direction": "up|down", "amount": int}.\n\n'
            f"Task: {task}\n\n"
            f"[Screenshot] data:image/png;base64,{encoded}"
        )
        response = await router.chat(
            [
                {"role": "system", "content": "You are a desktop automation planner."},
                {"role": "user", "content": prompt},
            ],
            [],
        )
        return getattr(response, "content", "") or ""

    async def execute(
        self,
        steps: list[PlannedStep],
        *,
        verify: bool = True,
    ) -> list[StepResult]:
        """Execute steps sequentially with verification and retry."""
        results: list[StepResult] = []
        for step in steps:
            result = await self._execute_step(step, verify=verify)
            results.append(result)
            if not result.ok:
                break
        return results

    async def _execute_step(self, step: PlannedStep, *, verify: bool) -> StepResult:
        last_detail = ""
        params = dict(step.params)
        for attempt in range(1, self.max_retries + 2):
            try:
                self._dispatch(step.action, params)
            except Exception as exc:
                last_detail = f"execution error: {exc}"
                params = self._adjust_params(params)
                continue
            verified = True
            if verify and step.expect:
                try:
                    image = self.agent.screenshot()
                    verified = await self.agent.analyzer.verify_action(step.expect, image)
                except Exception as exc:
                    last_detail = f"verification error: {exc}"
                    verified = False
            if verified:
                return StepResult(step=step, ok=True, attempts=attempt, verified=True, detail="ok")
            last_detail = "expected outcome not observed"
            params = self._adjust_params(params)
        return StepResult(step=step, ok=False, attempts=self.max_retries + 1, detail=last_detail)

    def _dispatch(self, action: str, params: dict[str, Any]) -> None:
        agent = self.agent
        if action == "click":
            agent.click(int(params["x"]), int(params["y"]), params.get("button", "left"))
        elif action == "double_click":
            agent.double_click(int(params["x"]), int(params["y"]))
        elif action == "right_click":
            agent.right_click(int(params["x"]), int(params["y"]))
        elif action == "move_to":
            agent.move_to(int(params["x"]), int(params["y"]))
        elif action == "drag":
            agent.drag(
                int(params["start_x"]),
                int(params["start_y"]),
                int(params["end_x"]),
                int(params["end_y"]),
            )
        elif action == "type_text":
            agent.type_text(str(params["text"]))
        elif action == "press_key":
            agent.press_key(str(params["key"]))
        elif action == "hotkey":
            agent.hotkey(*[str(k) for k in params["keys"]])
        elif action == "scroll":
            agent.scroll(str(params.get("direction", "down")), int(params.get("amount", 3)))
        elif action == "wait":
            time.sleep(float(params.get("seconds", 0.5)))
        else:
            raise ComputerUseError(f"Unknown planned action: {action}")

    @staticmethod
    def _adjust_params(params: dict[str, Any]) -> dict[str, Any]:
        """Nudge coordinates slightly for coordinate-based retries."""
        adjusted = dict(params)
        for key in ("x", "start_x", "end_x"):
            if key in adjusted:
                adjusted[key] = int(adjusted[key]) + 2
        for key in ("y", "start_y", "end_y"):
            if key in adjusted:
                adjusted[key] = int(adjusted[key]) + 2
        return adjusted


# --------------------------------------------------------------------------- #
# Session management (recording, safety, rate limiting)
# --------------------------------------------------------------------------- #
# Heuristics for destructive actions that require explicit confirmation.
_DESTRUCTIVE_HOTKEYS = {
    frozenset({"ctrl", "shift", "delete"}),
    frozenset({"ctrl", "alt", "delete"}),
    frozenset({"shift", "delete"}),
    frozenset({"super", "shift", "delete"}),
}
_DESTRUCTIVE_TEXT = re.compile(
    r"\b(rm\s+-rf|format\s+[a-z]:|del\s+/[sfq]|shutdown|mkfs|dd\s+if=)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ActionRecord:
    """Immutable-ish audit record of a single executed action."""

    action: str
    params: dict[str, Any]
    ok: bool
    detail: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "params": self.params,
            "ok": self.ok,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


class ComputerUseSession:
    """Manages a session of computer-use operations.

    Responsibilities:
      * record every action with timestamps (replay/audit),
      * enforce safety via allowed/blocked application lists and confirmation
        for destructive actions,
      * enforce a per-action timeout (default 30s) and a global rate limit
        (max 10 actions/second).
    """

    def __init__(
        self,
        *,
        session_id: str | None = None,
        agent: ComputerUseAgent | None = None,
        allowed_applications: list[str] | None = None,
        blocked_applications: list[str] | None = None,
        action_timeout: float = 30.0,
        max_actions_per_second: int = 10,
        require_confirmation: bool = True,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> None:
        self.session_id = session_id or str(uuid4())
        self.agent = agent or ComputerUseAgent()
        self.planner = ActionPlan(self.agent)
        self.allowed_applications = list(allowed_applications or [])
        self.blocked_applications = [a.lower() for a in (blocked_applications or [])]
        self.action_timeout = float(action_timeout)
        self.require_confirmation = require_confirmation
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.active = True
        self.created_at = datetime.now(UTC)
        self.history: list[ActionRecord] = []
        self._rate_limiter = RateLimiter(max_actions_per_second)
        self._lock = asyncio.Lock()

    # -- lifecycle -------------------------------------------------------- #
    def close(self) -> None:
        self.active = False

    def _ensure_active(self) -> None:
        if not self.active:
            raise ComputerUseError(f"Computer-use session closed: {self.session_id}")

    # -- safety ----------------------------------------------------------- #
    def check_application_allowed(self, application: str | None) -> None:
        """Validate the target application against allow/block lists."""
        if not application:
            return
        name = application.lower()
        if name in self.blocked_applications:
            raise ConfirmationRequiredError(
                "focus_application", f"application '{application}' is blocked by policy"
            )
        if self.allowed_applications and name not in [a.lower() for a in self.allowed_applications]:
            raise ConfirmationRequiredError(
                "focus_application",
                f"application '{application}' is not in the allow-list",
            )

    def is_destructive(self, action: str, params: dict[str, Any]) -> bool:
        """Heuristically decide whether an action is destructive."""
        if action == "hotkey":
            keys = frozenset(str(k).lower() for k in params.get("keys", []))
            if keys in _DESTRUCTIVE_HOTKEYS:
                return True
        if action == "type_text":
            if _DESTRUCTIVE_TEXT.search(str(params.get("text", ""))):
                return True
        if action == "press_key" and str(params.get("key", "")).lower() in {"delete"}:
            # Plain Delete is common; only flag when combined with shift via hotkey.
            return False
        return False

    # -- recording -------------------------------------------------------- #
    def _record(self, action: str, params: dict[str, Any], ok: bool, detail: str = "") -> ActionRecord:
        record = ActionRecord(action=action, params=params, ok=ok, detail=detail)
        self.history.append(record)
        return record

    # -- single action dispatch ------------------------------------------ #
    async def perform_action(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        *,
        confirmed: bool = False,
    ) -> ActionRecord:
        """Execute a single low-level action with safety + rate limiting."""
        self._ensure_active()
        params = dict(params or {})

        if self.require_confirmation and self.is_destructive(action, params) and not confirmed:
            self._record(action, params, False, "confirmation required")
            raise ConfirmationRequiredError(action, "destructive action requires confirmation")

        if action == "focus_application":
            self.check_application_allowed(str(params.get("application", "")))

        await self._rate_limiter.acquire()

        async with self._lock:
            try:
                await asyncio.wait_for(
                    self._run_action(action, params), timeout=self.action_timeout
                )
            except ConfirmationRequiredError:
                raise
            except TimeoutError:
                return self._record(action, params, False, f"action timed out after {self.action_timeout}s")
            except Exception as exc:
                return self._record(action, params, False, f"action failed: {exc}")
        return self._record(action, params, True, "ok")

    async def _run_action(self, action: str, params: dict[str, Any]) -> None:
        agent = self.agent
        # Synchronous driver calls are offloaded to a worker thread so they
        # never block the event loop (GUI calls can be slow).
        loop = asyncio.get_running_loop()

        def _call() -> None:
            if action == "click":
                agent.click(int(params["x"]), int(params["y"]), params.get("button", "left"))
            elif action == "double_click":
                agent.double_click(int(params["x"]), int(params["y"]))
            elif action == "right_click":
                agent.right_click(int(params["x"]), int(params["y"]))
            elif action == "move_to":
                agent.move_to(int(params["x"]), int(params["y"]))
            elif action == "drag":
                agent.drag(
                    int(params["start_x"]),
                    int(params["start_y"]),
                    int(params["end_x"]),
                    int(params["end_y"]),
                )
            elif action == "type_text":
                agent.type_text(str(params["text"]))
            elif action == "press_key":
                agent.press_key(str(params["key"]))
            elif action == "hotkey":
                agent.hotkey(*[str(k) for k in params["keys"]])
            elif action == "scroll":
                agent.scroll(str(params.get("direction", "down")), int(params.get("amount", 3)))
            elif action == "screenshot":
                agent.screenshot()
            elif action == "focus_application":
                # Focusing is policy-checked already; no-op at driver level.
                return
            else:
                raise ComputerUseError(f"Unknown action: {action}")

        await loop.run_in_executor(None, _call)

    # -- high-level task execution --------------------------------------- #
    async def execute_task(
        self,
        task: str,
        *,
        confirmed: bool = False,
        verify: bool = True,
    ) -> dict[str, Any]:
        """Plan and execute a high-level task, recording every step."""
        self._ensure_active()
        try:
            steps = await asyncio.wait_for(self.planner.plan(task), timeout=self.action_timeout)
        except TimeoutError:
            self._record("plan", {"task": task}, False, "planning timed out")
            return {"task": task, "ok": False, "detail": "planning timed out", "steps": []}
        except Exception as exc:
            self._record("plan", {"task": task}, False, f"planning failed: {exc}")
            return {"task": task, "ok": False, "detail": f"planning failed: {exc}", "steps": []}

        self._record("plan", {"task": task, "steps": [s.to_dict() for s in steps]}, True, "plan created")

        step_results: list[dict[str, Any]] = []
        all_ok = True
        for step in steps:
            if self.require_confirmation and self.is_destructive(step.action, step.params) and not confirmed:
                self._record(step.action, step.params, False, "confirmation required")
                step_results.append(
                    {"step": step.to_dict(), "ok": False, "detail": "confirmation required"}
                )
                all_ok = False
                break
            record = await self.perform_action(step.action, step.params, confirmed=confirmed)
            verified = False
            if record.ok and verify and step.expect:
                try:
                    image = self.agent.screenshot()
                    verified = await self.agent.analyzer.verify_action(step.expect, image)
                except Exception:
                    verified = False
            step_results.append(
                {
                    "step": step.to_dict(),
                    "ok": record.ok,
                    "detail": record.detail,
                    "verified": verified,
                }
            )
            if not record.ok:
                all_ok = False
                break
        return {"task": task, "ok": all_ok, "steps": step_results}

    # -- inspection ------------------------------------------------------- #
    def screenshot(self) -> bytes:
        self._ensure_active()
        return self.agent.screenshot()

    def get_history(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self.history]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "active": self.active,
            "backend": self.agent.backend_name,
            "dry_run": self.agent.dry_run,
            "require_confirmation": self.require_confirmation,
            "action_timeout": self.action_timeout,
            "allowed_applications": self.allowed_applications,
            "blocked_applications": self.blocked_applications,
            "created_at": self.created_at.isoformat(),
            "action_count": len(self.history),
        }


# --------------------------------------------------------------------------- #
# Session store
# --------------------------------------------------------------------------- #
class ComputerUseSessionStore:
    """In-memory registry of active computer-use sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, ComputerUseSession] = {}

    def create(self, **kwargs: Any) -> ComputerUseSession:
        session = ComputerUseSession(**kwargs)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> ComputerUseSession | None:
        return self._sessions.get(session_id)

    def list(self) -> list[ComputerUseSession]:
        return list(self._sessions.values())

    def close(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.close()
        return True

    def remove(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.close()
            return True
        return False


computer_use_session_store = ComputerUseSessionStore()
