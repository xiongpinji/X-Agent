"""P2-04: PromptGuard — prompt injection detection & defense engine.

Architecture (Hermes Promptware defense reference):
- Pattern-based detection: regex signatures for known injection vectors
- Heuristic scoring: suspicion level based on signal density
- Chokepoint integration: tool output, memory recall, skill load, MCP discovery
- Configurable action: BLOCK / WARN / SANITIZE / PASS

Threat model:
1. Indirect injection via tool output (web scrape, file read, API response)
2. Memory poisoning (malicious content stored then recalled into context)
3. Skill/plugin payload (untrusted skill code containing injection strings)
4. MCP server description injection (tool descriptions with embedded instructions)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


class ScanVerdict(StrEnum):
    """Result of a prompt injection scan."""

    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


class GuardAction(StrEnum):
    """Action to take when injection is detected."""

    PASS = "pass"  # Log only, do not block
    WARN = "warn"  # Log + annotate response
    SANITIZE = "sanitize"  # Strip suspicious content
    BLOCK = "block"  # Reject entirely


@dataclass
class ScanSignal:
    """A single detection signal."""

    pattern_id: str
    description: str
    severity: float  # 0.0 - 1.0
    matched_text: str = ""


@dataclass
class ScanResult:
    """Result of scanning content for prompt injection."""

    verdict: ScanVerdict
    confidence: float  # 0.0 - 1.0
    signals: list[ScanSignal] = field(default_factory=list)
    sanitized_text: str | None = None
    source: str = ""  # chokepoint identifier

    @property
    def is_safe(self) -> bool:
        return self.verdict == ScanVerdict.SAFE

    @property
    def is_malicious(self) -> bool:
        return self.verdict == ScanVerdict.MALICIOUS


# --- Detection Patterns ---
# Each pattern: (id, description, severity, compiled_regex)

_INJECTION_PATTERNS: list[tuple[str, str, float, re.Pattern[str]]] = [
    # Role hijacking
    (
        "ROLE_HIJACK_01",
        "Attempts to override system role",
        0.9,
        re.compile(
            r"(?i)(you are now|act as|pretend to be|from now on you|new role:|"
            r"system:\s*you|ignore (all )?(previous|prior|above) (instructions|prompts|rules))",
        ),
    ),
    # Instruction override
    (
        "INSTR_OVERRIDE_01",
        "Attempts to override system instructions",
        0.85,
        re.compile(
            r"(?i)(disregard (all )?(previous|prior|above)|forget (all )?(your|the) (rules|instructions|constraints)|"
            r"override (system|safety|security)|bypass (filter|guard|restriction))",
        ),
    ),
    # Delimiter injection
    (
        "DELIM_INJECT_01",
        "Injects fake message delimiters",
        0.8,
        re.compile(
            r"(?i)(<\|?(system|user|assistant|im_start|im_end)\|?>|"
            r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>|"
            r"###\s*(system|instruction|human|assistant))",
        ),
    ),
    # Data exfiltration attempt
    (
        "EXFIL_01",
        "Attempts to extract system prompt or secrets",
        0.85,
        re.compile(
            r"(?i)(reveal|show|print|output|repeat|echo) (your|the|system) "
            r"(system prompt|instructions|initial prompt|hidden prompt|secret|api[_ ]?key|password|token)",
        ),
    ),
    # Encoding evasion
    (
        "ENCODING_01",
        "Uses encoding to evade detection",
        0.7,
        re.compile(
            r"(?i)(base64[ _]?(decode|encode)|rot13|hex[ _]?decode|"
            r"\\x[0-9a-f]{2}\\x[0-9a-f]{2}\\x[0-9a-f]{2}|"
            r"&#x?[0-9a-f]+;.*&#x?[0-9a-f]+;.*&#x?[0-9a-f]+;)",
        ),
    ),
    # Jailbreak templates
    (
        "JAILBREAK_01",
        "Known jailbreak template patterns",
        0.9,
        re.compile(
            r"(?i)(DAN mode|developer mode|do anything now|"
            r"jailbreak|AIM bot|always intelligent|unfiltered mode|"
            r"no restrictions|unrestricted mode|god mode)",
        ),
    ),
    # Prompt leaking
    (
        "LEAK_01",
        "Attempts to leak conversation context",
        0.75,
        re.compile(
            r"(?i)(what (are|were) your (original|initial|system) (instructions|prompt|message)|"
            r"repeat (everything|all|the text) (above|before|so far)|"
            r"output (your|the) (full|complete|entire) (prompt|instructions|context))",
        ),
    ),
    # Tool abuse instruction
    (
        "TOOL_ABUSE_01",
        "Instructs agent to misuse tools",
        0.8,
        re.compile(
            r"(?i)(execute|run|call|invoke) .{0,50}(rm -rf|format|delete all|"
            r"drop table|truncate|shutdown|reboot|kill process|"
            r"curl .*\| ?(ba)?sh|wget .*\| ?(ba)?sh)",
        ),
    ),
    # Social engineering
    (
        "SOCIAL_ENG_01",
        "Social engineering manipulation",
        0.6,
        re.compile(
            r"(?i)(this is (a|an) (emergency|urgent|critical)|"
            r"you must (comply|obey|do this|help me)|"
            r"I (am|'m) (the|your) (admin|developer|creator|owner)|"
            r"failure to comply will (result|lead|cause))",
        ),
    ),
    # Multi-turn injection (continuation attack)
    (
        "MULTI_TURN_01",
        "Attempts to continue from a fake prior turn",
        0.75,
        re.compile(
            r"(?i)(as (I|we) (discussed|agreed|decided) (earlier|before|previously)|"
            r"continuing from (our|the) (last|previous) (conversation|session)|"
            r"you (already|previously) (agreed|promised|said|confirmed))",
        ),
    ),
]


class PromptGuard:
    """Prompt injection detection engine with configurable thresholds.

    Usage:
        guard = PromptGuard()
        result = guard.scan(tool_output, source="tool:web_search")
        if result.is_malicious:
            # block or sanitize
    """

    def __init__(
        self,
        *,
        suspicious_threshold: float = 0.4,
        malicious_threshold: float = 0.7,
        default_action: GuardAction = GuardAction.WARN,
        enabled: bool = True,
        whitelist_sources: list[str] | None = None,
    ) -> None:
        self.suspicious_threshold = suspicious_threshold
        self.malicious_threshold = malicious_threshold
        self.default_action = default_action
        self.enabled = enabled
        self.whitelist_sources = set(whitelist_sources or [])
        self._scan_count = 0
        self._detection_count = 0

    def scan(self, text: str, *, source: str = "unknown") -> ScanResult:
        """Scan text for prompt injection patterns.

        Args:
            text: Content to scan
            source: Identifier for the chokepoint (e.g. "tool:web_search", "memory:recall")

        Returns:
            ScanResult with verdict, confidence, and signals
        """
        self._scan_count += 1

        if not self.enabled or not text:
            return ScanResult(verdict=ScanVerdict.SAFE, confidence=1.0, source=source)

        # Whitelist bypass
        if source in self.whitelist_sources:
            return ScanResult(verdict=ScanVerdict.SAFE, confidence=1.0, source=source)

        signals: list[ScanSignal] = []
        max_severity = 0.0

        for pattern_id, description, severity, regex in _INJECTION_PATTERNS:
            match = regex.search(text)
            if match:
                signals.append(
                    ScanSignal(
                        pattern_id=pattern_id,
                        description=description,
                        severity=severity,
                        matched_text=match.group(0)[:100],
                    )
                )
                max_severity = max(max_severity, severity)

        # Compute confidence based on signal density and max severity
        if not signals:
            return ScanResult(verdict=ScanVerdict.SAFE, confidence=1.0, source=source)

        self._detection_count += 1
        signal_density = len(signals) / max(len(text.split()) / 100, 1)
        confidence = min(max_severity * (1 + signal_density * 0.1), 1.0)

        # Determine verdict
        if confidence >= self.malicious_threshold:
            verdict = ScanVerdict.MALICIOUS
        elif confidence >= self.suspicious_threshold:
            verdict = ScanVerdict.SUSPICIOUS
        else:
            verdict = ScanVerdict.SAFE

        if verdict != ScanVerdict.SAFE:
            logger.warning(
                "PromptGuard detection [%s] source=%s confidence=%.2f signals=%d",
                verdict.value,
                source,
                confidence,
                len(signals),
            )

        return ScanResult(
            verdict=verdict,
            confidence=confidence,
            signals=signals,
            source=source,
        )

    def scan_and_sanitize(self, text: str, *, source: str = "unknown") -> tuple[ScanResult, str]:
        """Scan and return sanitized text (strips matched patterns if malicious).

        Returns:
            Tuple of (ScanResult, sanitized_text)
        """
        result = self.scan(text, source=source)

        if result.verdict != ScanVerdict.MALICIOUS:
            return result, text

        # Sanitize: replace matched patterns with [REDACTED]
        sanitized = text
        for signal in result.signals:
            for pattern_id, _, _, regex in _INJECTION_PATTERNS:
                if pattern_id == signal.pattern_id:
                    sanitized = regex.sub("[CONTENT_REDACTED]", sanitized)
                    break

        result.sanitized_text = sanitized
        return result, sanitized

    def scan_tool_output(self, tool_name: str, output: Any) -> ScanResult:
        """Scan tool execution output (chokepoint: tool output)."""
        text = str(output) if output is not None else ""
        return self.scan(text, source=f"tool:{tool_name}")

    def scan_memory_content(self, memory_id: str, content: str) -> ScanResult:
        """Scan recalled memory content (chokepoint: memory recall)."""
        return self.scan(content, source=f"memory:{memory_id}")

    def scan_mcp_description(self, server_name: str, description: str) -> ScanResult:
        """Scan MCP tool description (chokepoint: MCP discovery)."""
        return self.scan(description, source=f"mcp:{server_name}")

    def scan_skill_content(self, skill_name: str, content: str) -> ScanResult:
        """Scan skill definition content (chokepoint: skill load)."""
        return self.scan(content, source=f"skill:{skill_name}")

    @property
    def stats(self) -> dict[str, int]:
        """Return scan statistics."""
        return {
            "total_scans": self._scan_count,
            "detections": self._detection_count,
            "detection_rate_pct": (
                round(self._detection_count / self._scan_count * 100, 2)
                if self._scan_count > 0
                else 0
            ),
        }


@lru_cache
def get_prompt_guard() -> PromptGuard:
    """Get the global PromptGuard instance (configured from settings)."""
    from backend.app.settings import get_settings

    settings = get_settings()
    return PromptGuard(
        suspicious_threshold=getattr(settings, "prompt_guard_suspicious_threshold", 0.4),
        malicious_threshold=getattr(settings, "prompt_guard_malicious_threshold", 0.7),
        default_action=GuardAction(
            getattr(settings, "prompt_guard_action", "warn")
        ),
        enabled=getattr(settings, "prompt_guard_enabled", True),
    )
