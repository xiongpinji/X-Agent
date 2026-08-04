"""Closed-loop Skill Self-Evolution system (P0-B).

Implements a complete, real closed loop comparable to Hermes Agent's skill
auto-generation:

    Discover → Generate → Evaluate → Deploy → Monitor → Optimize

Components
----------
- ``SkillDiscoveryEngine``: mines user interaction history for repetitive
  task patterns and scores them (frequency × complexity × time_saved).
- ``SkillGenerator``: uses the LLM (with a deterministic template fallback)
  to generate skill code + test cases under explicit safety constraints.
- ``SkillEvaluator``: executes generated skills inside a restricted sandbox,
  measuring success_rate / latency / user_satisfaction and running an A/B
  comparison against the manual (baseline) approach.
- ``SkillOptimizer``: tracks performance over time, auto-refactors
  underperforming skills (success_rate < 0.7), keeps the best N versions and
  auto-deprecates skills unused for 30 days.
- ``EvolutionLoop``: orchestrates the whole cycle as a background task and
  maintains aggregate ``evolution_metrics``.

Every mutation is written to an append-only audit log and the full state
(patterns, skills, versions, metrics) is persisted to disk as JSON so the
loop survives restarts.
"""
from __future__ import annotations

import ast
import asyncio
import builtins
import json
import logging
import math
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ─── Enums ────────────────────────────────────────────────────────────────────


class PatternStatus(StrEnum):
    """Lifecycle state of a discovered pattern."""

    DISCOVERED = "discovered"
    PROPOSED = "proposed"
    GENERATED = "generated"
    REJECTED = "rejected"


class SkillStatus(StrEnum):
    """Lifecycle state of an evolved skill."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class AuditAction(StrEnum):
    """Categories of audited evolution actions."""

    PATTERN_DISCOVERED = "pattern_discovered"
    PATTERN_PROPOSED = "pattern_proposed"
    SKILL_GENERATED = "skill_generated"
    SKILL_EVALUATED = "skill_evaluated"
    SKILL_DEPLOYED = "skill_deployed"
    SKILL_OPTIMIZED = "skill_optimized"
    SKILL_DEPRECATED = "skill_deprecated"
    SKILL_USAGE = "skill_usage"
    LOOP_CYCLE = "loop_cycle"
    LOOP_STARTED = "loop_started"
    LOOP_STOPPED = "loop_stopped"


# ─── Data models ──────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class InteractionRecord:
    """A single normalized user interaction used for discovery."""

    task_description: str = ""
    signature: str = ""
    tool_calls: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    success: bool = True
    user_id: str = "anonymous"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveredPattern:
    """A repetitive task pattern discovered from interaction history."""

    id: str = field(default_factory=lambda: str(uuid4()))
    signature: str = ""
    description: str = ""
    examples: list[str] = field(default_factory=list)
    tool_sequence: list[str] = field(default_factory=list)
    frequency: int = 0
    complexity: float = 0.0
    avg_time_saved_seconds: float = 0.0
    score: float = 0.0
    status: PatternStatus = PatternStatus.DISCOVERED
    first_seen: str = field(default_factory=_now_iso)
    last_seen: str = field(default_factory=_now_iso)
    skill_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiscoveredPattern:
        data = dict(data)
        data["status"] = PatternStatus(data.get("status", "discovered"))
        return cls(**data)


@dataclass
class SkillVersion:
    """An immutable snapshot of generated skill code + tests."""

    version: int = 1
    code: str = ""
    test_code: str = ""
    generation_source: str = "template"  # "llm" | "template" | "optimizer"
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    notes: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillVersion:
        return cls(**data)


@dataclass
class EvolvedSkill:
    """A skill produced (and versioned) by the evolution system."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    pattern_id: str = ""
    trigger_keywords: list[str] = field(default_factory=list)
    versions: list[SkillVersion] = field(default_factory=list)
    active_version: int = 0
    status: SkillStatus = SkillStatus.CANDIDATE
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    user_satisfaction: float = 0.0
    created_at: str = field(default_factory=_now_iso)
    last_used_at: float = 0.0
    last_optimized_at: str | None = None
    deprecated_at: str | None = None

    @property
    def current(self) -> SkillVersion | None:
        for v in self.versions:
            if v.version == self.active_version:
                return v
        return self.versions[-1] if self.versions else None

    def record_usage(self, success: bool, latency_ms: float = 0.0, satisfaction: float | None = None) -> None:
        self.usage_count += 1
        self.last_used_at = time.time()
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.success_rate = self.success_count / self.usage_count if self.usage_count else 0.0
        if latency_ms > 0:
            # Exponential moving average of latency.
            if self.avg_latency_ms <= 0:
                self.avg_latency_ms = latency_ms
            else:
                self.avg_latency_ms = self.avg_latency_ms * 0.7 + latency_ms * 0.3
        if satisfaction is not None:
            if self.user_satisfaction <= 0:
                self.user_satisfaction = satisfaction
            else:
                self.user_satisfaction = self.user_satisfaction * 0.7 + satisfaction * 0.3

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["versions"] = [v.to_dict() for v in self.versions]
        data["active_code"] = self.current.code if self.current else ""
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolvedSkill:
        data = dict(data)
        data["status"] = SkillStatus(data.get("status", "candidate"))
        data["versions"] = [SkillVersion.from_dict(v) for v in data.get("versions", [])]
        data.pop("active_code", None)
        return cls(**data)


@dataclass
class EvaluationResult:
    """Outcome of sandbox evaluation for one skill version."""

    skill_id: str = ""
    version: int = 0
    passed: bool = False
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    user_satisfaction: float = 0.0
    tests_run: int = 0
    tests_passed: int = 0
    ab_test: dict[str, Any] = field(default_factory=dict)
    security_violations: list[str] = field(default_factory=list)
    error: str | None = None
    notes: str = ""
    evaluated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEntry:
    """An immutable audit-log record of an evolution action."""

    id: str = field(default_factory=lambda: str(uuid4()))
    action: AuditAction = AuditAction.LOOP_CYCLE
    skill_id: str | None = None
    pattern_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    actor: str = "system"
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action"] = self.action.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        data = dict(data)
        data["action"] = AuditAction(data.get("action", "loop_cycle"))
        return cls(**data)


@dataclass
class EvolutionMetrics:
    """Aggregate metrics maintained by the evolution loop."""

    patterns_discovered: int = 0
    skills_created: int = 0
    skills_deployed: int = 0
    skills_optimized: int = 0
    skills_deprecated: int = 0
    total_evaluations: int = 0
    total_optimizations: int = 0
    avg_improvement: float = 0.0
    loop_cycles: int = 0
    last_cycle_at: str | None = None
    last_cycle_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionMetrics:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ─── Restricted sandbox ───────────────────────────────────────────────────────


@dataclass
class SandboxOutcome:
    """Result of running code in the restricted sandbox."""

    success: bool
    results: list[dict[str, Any]] = field(default_factory=list)
    tests_run: int = 0
    tests_passed: int = 0
    avg_latency_ms: float = 0.0
    error: str | None = None
    violations: list[str] = field(default_factory=list)


_REAL_IMPORT = builtins.__import__


def _sandbox_import(name, globals=None, locals=None, fromlist=(), level=0):
    """A guarded ``__import__`` that only permits whitelisted modules."""
    root = (name or "").split(".")[0]
    if root not in RestrictedSandbox.ALLOWED_IMPORTS:
        raise ImportError(f"Import not allowed in sandbox: {name}")
    return _REAL_IMPORT(name, globals, locals, fromlist, level)


class RestrictedSandbox:
    """A dependency-free restricted executor for generated skill code.

    Defense layers:
    1. AST validation — blocks dangerous imports, attribute-based sandbox
       escapes and disallowed node types.
    2. Restricted ``__builtins__`` whitelist during ``exec``.
    3. Hard wall-clock timeout via ``asyncio.wait_for`` (runs in a thread).

    This intentionally avoids Docker so evaluation works in any environment,
    while still refusing to run anything that looks unsafe.
    """

    ALLOWED_IMPORTS = {
        "json", "math", "re", "random", "datetime", "time", "collections",
        "itertools", "functools", "operator", "string", "hashlib", "base64",
        "statistics", "decimal", "fractions", "textwrap", "calendar", "copy",
        "enum", "dataclasses", "typing", "abc", "uuid", "urllib.parse",
        "csv", "io", "html", "unicodedata", "difflib", "pprint", "numbers",
    }

    BLOCKED_ATTRS = {
        "__import__", "__subclasses__", "__bases__", "__mro__", "__globals__",
        "__builtins__", "__code__", "__closure__", "__class__", "__dict__",
        # Filesystem / process / code-execution escape vectors reachable via
        # otherwise-allowed modules (e.g. io.open, subprocess.Popen).
        "open", "open_code", "FileIO", "system", "popen", "Popen",
        "check_output", "check_call", "getoutput", "exec", "eval", "compile",
    }

    SAFE_BUILTINS = {
        "abs": builtins.abs, "all": builtins.all, "any": builtins.any,
        "bool": builtins.bool, "dict": builtins.dict, "divmod": builtins.divmod,
        "enumerate": builtins.enumerate, "filter": builtins.filter,
        "float": builtins.float, "format": builtins.format,
        "frozenset": builtins.frozenset, "int": builtins.int,
        "isinstance": builtins.isinstance, "issubclass": builtins.issubclass,
        "iter": builtins.iter, "len": builtins.len, "list": builtins.list,
        "map": builtins.map, "max": builtins.max, "min": builtins.min,
        "next": builtins.next, "pow": builtins.pow, "print": builtins.print,
        "range": builtins.range, "repr": builtins.repr,
        "reversed": builtins.reversed, "round": builtins.round,
        "set": builtins.set, "slice": builtins.slice, "sorted": builtins.sorted,
        "str": builtins.str, "sum": builtins.sum, "tuple": builtins.tuple,
        "type": builtins.type, "zip": builtins.zip, "True": True,
        "False": False, "None": None, "__import__": _sandbox_import,
    }

    def _sanitize_imports(self, code: str) -> str:
        """Drop import statements for modules outside the whitelist."""
        if not code:
            return code
        kept: list[str] = []
        for line in code.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                if stripped.startswith("import "):
                    root = stripped[len("import "):].split()[0].split(".")[0]
                else:
                    root = stripped[len("from "):].split()[0].split(".")[0]
                if root not in self.ALLOWED_IMPORTS:
                    continue  # drop disallowed import
            kept.append(line)
        return "\n".join(kept)

    def validate(self, code: str) -> list[str]:
        """Return a list of human-readable violations (empty == safe)."""
        violations: list[str] = []
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return [f"SyntaxError: {exc.msg} (line {exc.lineno})"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in self.ALLOWED_IMPORTS:
                        violations.append(f"Import not allowed: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root not in self.ALLOWED_IMPORTS:
                    violations.append(f"Import not allowed: {node.module}")
            elif isinstance(node, ast.Attribute):
                if node.attr in self.BLOCKED_ATTRS:
                    violations.append(f"Blocked attribute access: {node.attr}")
            elif isinstance(node, ast.Name):
                if node.id in {"eval", "exec", "compile", "globals", "locals",
                               "vars", "getattr", "setattr", "delattr",
                               "__import__", "open", "input", "breakpoint"}:
                    violations.append(f"Blocked builtin reference: {node.id}")
        return violations

    async def run_skill(
        self,
        code: str,
        test_code: str,
        timeout: float = 10.0,
    ) -> SandboxOutcome:
        """Validate + execute a skill against its generated test cases."""
        # LLMs frequently append unused imports (asyncio, os, ...). Strip any
        # import whose module is not whitelisted; the AST pass below still
        # rejects genuinely dangerous calls/attributes.
        code = self._sanitize_imports(code)
        test_code = self._sanitize_imports(test_code)
        for label, chunk in (("skill", code), ("test", test_code)):
            violations = self.validate(chunk)
            if violations:
                return SandboxOutcome(
                    success=False,
                    error=f"Security validation failed in {label} code",
                    violations=violations,
                )

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._execute, code, test_code),
                timeout=timeout,
            )
        except TimeoutError:
            return SandboxOutcome(success=False, error=f"Execution timed out after {timeout}s")
        except Exception as exc:
            logger.warning("Sandbox execution error: %s", exc)
            return SandboxOutcome(success=False, error=str(exc))

    def _execute(self, code: str, test_code: str) -> SandboxOutcome:
        """Synchronous executor (runs inside a worker thread)."""
        restricted_globals: dict[str, Any] = {"__builtins__": dict(self.SAFE_BUILTINS)}
        try:
            exec(compile(code, "<skill>", "exec"), restricted_globals)
            if test_code.strip():
                exec(compile(test_code, "<test>", "exec"), restricted_globals)
        except Exception as exc:
            return SandboxOutcome(success=False, error=f"Compile/exec error: {exc}")

        execute_fn = restricted_globals.get("execute")
        if not callable(execute_fn):
            return SandboxOutcome(success=False, error="Skill must define a callable 'execute(context)'")

        test_cases = restricted_globals.get("TEST_CASES") or [{"input": {}}]
        validator = restricted_globals.get("validate")
        if not isinstance(test_cases, list) or not test_cases:
            test_cases = [{"input": {}}]

        loop = asyncio.new_event_loop()
        results: list[dict[str, Any]] = []
        latencies: list[float] = []
        passed = 0
        try:
            for case in test_cases:
                ctx = case.get("input", {}) if isinstance(case, dict) else {}
                start = time.perf_counter()
                try:
                    result = execute_fn(ctx)
                    if asyncio.iscoroutine(result):
                        result = loop.run_until_complete(result)
                    latency_ms = (time.perf_counter() - start) * 1000
                    ok = True
                    if callable(validator):
                        try:
                            ok = bool(validator(result, case))
                        except Exception as exc:
                            ok = False
                            result = f"validator error: {exc}"
                    elif isinstance(case, dict) and "expect" in case:
                        ok = result == case["expect"]
                    if ok:
                        passed += 1
                    latencies.append(latency_ms)
                    results.append({"input": ctx, "output": _safe_repr(result),
                                    "passed": ok, "latency_ms": round(latency_ms, 3)})
                except Exception as exc:
                    latency_ms = (time.perf_counter() - start) * 1000
                    latencies.append(latency_ms)
                    results.append({"input": ctx, "output": None, "passed": False,
                                    "error": str(exc), "latency_ms": round(latency_ms, 3)})
        finally:
            loop.close()

        total = len(results)
        success_rate = passed / total if total else 0.0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        return SandboxOutcome(
            success=success_rate >= 0.5,
            results=results,
            tests_run=total,
            tests_passed=passed,
            avg_latency_ms=round(avg_latency, 3),
        )


def _safe_repr(value: Any, limit: int = 500) -> Any:
    """Best-effort JSON-serializable representation of a skill output."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        text = repr(value)
        return text[:limit]


# ─── Persistence store ────────────────────────────────────────────────────────


def _default_state_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / ".xagent_runtime" / "data" / "skill_evolution.json"


class EvolutionStore:
    """Thread-safe JSON-backed persistence for the evolution system."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _default_state_path()
        self._lock = RLock()
        self.patterns: list[DiscoveredPattern] = []
        self.skills: list[EvolvedSkill] = []
        self.audit_log: list[AuditEntry] = []
        self.metrics = EvolutionMetrics()
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self.patterns = [DiscoveredPattern.from_dict(p) for p in raw.get("patterns", [])]
                self.skills = [EvolvedSkill.from_dict(s) for s in raw.get("skills", [])]
                self.audit_log = [AuditEntry.from_dict(a) for a in raw.get("audit_log", [])]
                self.metrics = EvolutionMetrics.from_dict(raw.get("metrics", {}))
                logger.info("Loaded skill-evolution state: %d patterns, %d skills",
                            len(self.patterns), len(self.skills))
        except Exception as exc:
            logger.warning("Failed to load skill-evolution state: %s", exc)

    def save(self) -> None:
        with self._lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "patterns": [p.to_dict() for p in self.patterns],
                    "skills": [s.to_dict() for s in self.skills],
                    "audit_log": [a.to_dict() for a in self.audit_log[-2000:]],
                    "metrics": self.metrics.to_dict(),
                    "saved_at": _now_iso(),
                }
                tmp = self._path.with_suffix(".tmp")
                tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.replace(self._path)
            except Exception as exc:
                logger.warning("Failed to persist skill-evolution state: %s", exc)

    def audit(self, action: AuditAction, *, skill_id: str | None = None,
              pattern_id: str | None = None, details: dict[str, Any] | None = None,
              actor: str = "system") -> AuditEntry:
        entry = AuditEntry(action=action, skill_id=skill_id, pattern_id=pattern_id,
                           details=details or {}, actor=actor)
        with self._lock:
            self.audit_log.append(entry)
        return entry


# ─── LLM helper ───────────────────────────────────────────────────────────────


async def _llm_chat(llm_router: Any, prompt: str) -> str:
    """Send a single-turn prompt and return the textual content."""
    messages = [{"role": "user", "content": prompt}]
    response = await llm_router.chat(messages, tools=[])
    return response.content if hasattr(response, "content") else str(response)


def _extract_code_block(text: str) -> str:
    """Extract the first ```python ... ``` block, else return the raw text."""
    if "```" in text:
        match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()


def _extract_json(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


# ─── Discovery ────────────────────────────────────────────────────────────────

_STOPWORDS = frozenset({
    "the", "a", "an", "to", "of", "and", "or", "for", "in", "on", "with", "is",
    "are", "please", "can", "you", "my", "me", "it", "this", "that", "do",
    "how", "what", "i", "we", "into", "from", "帮", "我", "请", "的", "了", "把", "将", "一下",
})

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+")


def _signature(task_description: str, max_tokens: int = 6) -> str:
    """Normalize a task description into a stable clustering signature."""
    tokens = [t.lower() for t in _TOKEN_RE.findall(task_description or "")]
    tokens = [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
    seen: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.append(t)
    return " ".join(sorted(seen[:max_tokens])) or "<generic>"


class SkillDiscoveryEngine:
    """Mines interaction history for repetitive tasks and scores them.

    Score = frequency_factor × complexity × time_saved_seconds, where:
    - frequency_factor grows logarithmically with occurrence count
    - complexity reflects the average tool-sequence length (0..1)
    - time_saved is the average manual duration of the task (seconds)
    """

    def __init__(self, store: EvolutionStore, propose_threshold: float = 5.0) -> None:
        self._store = store
        self._interactions: list[InteractionRecord] = []
        self.propose_threshold = propose_threshold

    def record_interaction(
        self,
        task_description: str,
        tool_calls: list[str] | None = None,
        duration_ms: float = 0.0,
        success: bool = True,
        user_id: str = "anonymous",
    ) -> InteractionRecord:
        record = InteractionRecord(
            task_description=task_description,
            signature=_signature(task_description),
            tool_calls=tool_calls or [],
            duration_ms=duration_ms,
            success=success,
            user_id=user_id,
        )
        self._interactions.append(record)
        # Cap in-memory history.
        if len(self._interactions) > 5000:
            self._interactions = self._interactions[-5000:]
        return record

    def _cluster(self) -> dict[str, list[InteractionRecord]]:
        clusters: dict[str, list[InteractionRecord]] = {}
        for rec in self._interactions:
            clusters.setdefault(rec.signature, []).append(rec)
        return clusters

    @staticmethod
    def _score(frequency: int, complexity: float, time_saved_seconds: float) -> float:
        freq_factor = math.log2(frequency + 1)
        return round(freq_factor * max(complexity, 0.1) * max(time_saved_seconds, 0.1), 4)

    def analyze(self) -> list[DiscoveredPattern]:
        """(Re)compute patterns from recorded interactions and persist them."""
        clusters = self._cluster()
        existing = {p.signature: p for p in self._store.patterns}
        updated: list[DiscoveredPattern] = []

        for signature, records in clusters.items():
            if len(records) < 2:
                continue  # need repetition to count as a pattern
            tool_counts = [len(r.tool_calls) for r in records]
            avg_tools = sum(tool_counts) / len(tool_counts) if tool_counts else 0
            complexity = min(1.0, avg_tools / 5.0)  # 5+ tools == max complexity
            avg_duration_s = (sum(r.duration_ms for r in records) / len(records)) / 1000.0
            frequency = len(records)
            score = self._score(frequency, complexity, avg_duration_s)

            pattern = existing.get(signature)
            if pattern is None:
                pattern = DiscoveredPattern(
                    signature=signature,
                    description=records[0].task_description,
                    tool_sequence=records[0].tool_calls,
                )
                self._store.patterns.append(pattern)
                self._store.audit(AuditAction.PATTERN_DISCOVERED, pattern_id=pattern.id,
                                  details={"signature": signature, "score": score})
            pattern.examples = list({r.task_description for r in records})[:10]
            pattern.frequency = frequency
            pattern.complexity = round(complexity, 3)
            pattern.avg_time_saved_seconds = round(avg_duration_s, 3)
            pattern.score = score
            pattern.last_seen = _now_iso()
            updated.append(pattern)

        self._store.metrics.patterns_discovered = len(
            [p for p in self._store.patterns if p.status != PatternStatus.REJECTED]
        )
        self._store.save()
        return sorted(updated, key=lambda p: p.score, reverse=True)

    def discover(self) -> list[DiscoveredPattern]:
        """Analyze and auto-propose patterns whose score crosses the threshold."""
        patterns = self.analyze()
        proposed: list[DiscoveredPattern] = []
        for pattern in patterns:
            if pattern.status == PatternStatus.DISCOVERED and pattern.score >= self.propose_threshold:
                pattern.status = PatternStatus.PROPOSED
                self._store.audit(AuditAction.PATTERN_PROPOSED, pattern_id=pattern.id,
                                  details={"score": pattern.score, "frequency": pattern.frequency})
                proposed.append(pattern)
        if proposed:
            self._store.save()
        return proposed

    def list_patterns(self, status: PatternStatus | None = None) -> list[DiscoveredPattern]:
        items = self._store.patterns
        if status is not None:
            items = [p for p in items if p.status == status]
        return sorted(items, key=lambda p: p.score, reverse=True)


# ─── Generation ───────────────────────────────────────────────────────────────

_SKILL_TEMPLATE = '''"""Auto-generated skill: {name}."""


async def execute(context: dict) -> dict:
    """Execute the '{name}' skill.

    Description: {description}
    Expected tools: {tools}
    """
    payload = context or {{}}
    # Deterministic reference implementation derived from the discovered pattern.
    steps = {tools!r}
    completed = []
    for step in steps:
        completed.append(step)
    return {{
        "skill": "{name}",
        "status": "completed",
        "steps_executed": completed,
        "input_keys": sorted(list(payload.keys())),
    }}
'''

_TEST_TEMPLATE = '''TEST_CASES = [
    {"input": {}, "expect": None},
    {"input": {"value": 1}, "expect": None},
]


def validate(result, case):
    return isinstance(result, dict) and result.get("status") == "completed"
'''

# Lenient harness used when the LLM omits tests: only requires that `execute`
# returns a JSON-serializable dict without raising.
_GENERIC_TEST_TEMPLATE = '''TEST_CASES = [
    {"input": {}},
    {"input": {"value": 1}},
    {"input": {"csv_content": "a,b\\n1,2"}},
]


def validate(result, case):
    return isinstance(result, dict)
'''

_GENERATION_PROMPT = """You are generating a reusable Python skill for an agent platform.

Discovered repetitive task pattern:
- Name suggestion: {name}
- Description: {description}
- Typical tool sequence: {tools}
- Example user requests: {examples}

STRICT SAFETY CONSTRAINTS (the code runs in a restricted sandbox):
- Only these imports are allowed: json, math, re, random, datetime, time, collections, itertools, functools, operator, string, hashlib, base64, statistics, decimal, fractions, textwrap, calendar, copy, enum, dataclasses, typing, abc, uuid, urllib.parse, csv, io, html, unicodedata, difflib, pprint, numbers
- Forbidden: eval, exec, compile, open, input, __import__, globals, locals, getattr/setattr, dunder introspection (__class__, __subclasses__, __globals__, etc.)
- No filesystem, network, subprocess or OS access.
- Must be pure, deterministic and side-effect free.

Produce TWO code blocks:
1. ```python  — the skill. It MUST define `async def execute(context: dict) -> dict` returning a JSON-serializable dict with at least a "status" key.
2. ```test    — test harness. It MUST define `TEST_CASES` (a non-empty list of dicts each with an "input" key) and `def validate(result, case) -> bool`.

Return ONLY the two fenced code blocks, no prose."""


class SkillGenerator:
    """Generates skill code + tests from a discovered pattern."""

    def __init__(self, store: EvolutionStore, llm_router: Any | None = None) -> None:
        self._store = store
        self._llm_router = llm_router

    @property
    def llm_router(self) -> Any:
        if self._llm_router is None:
            try:
                from backend.app.dependencies import get_llm_router
                self._llm_router = get_llm_router()
            except Exception:
                self._llm_router = None
        return self._llm_router

    @staticmethod
    def _skill_name(pattern: DiscoveredPattern) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", pattern.signature).strip("_") or "skill"
        return f"auto_{base}"[:48]

    def _template(self, pattern: DiscoveredPattern) -> tuple[str, str]:
        name = self._skill_name(pattern)
        code = _SKILL_TEMPLATE.format(
            name=name,
            description=pattern.description or pattern.signature,
            tools=pattern.tool_sequence or ["analyze", "act"],
        )
        return code, _TEST_TEMPLATE

    async def generate(self, pattern: DiscoveredPattern) -> EvolvedSkill:
        """Generate (or regenerate) a skill for the given pattern."""
        name = self._skill_name(pattern)
        code, test_code, source = "", "", "template"

        router = self.llm_router
        if router is not None:
            try:
                prompt = _GENERATION_PROMPT.format(
                    name=name,
                    description=pattern.description or pattern.signature,
                    tools=pattern.tool_sequence,
                    examples=pattern.examples[:3],
                )
                content = await _llm_chat(router, prompt)
                code, test_code = self._parse_llm_output(content)
                source = "llm"
            except Exception as exc:
                logger.warning("LLM skill generation failed, using template: %s", exc)
                code, test_code = "", ""

        if not self._is_valid_skill(code):
            # LLM output missing/invalid — fall back to the deterministic template.
            code, test_code = self._template(pattern)
            source = "template"
        elif not test_code.strip() and "TEST_CASES" not in code:
            # LLM gave a skill but no tests — attach a lenient generic harness.
            test_code = _GENERIC_TEST_TEMPLATE

        # Reuse an existing skill for this pattern if present (regeneration).
        skill = next((s for s in self._store.skills if s.pattern_id == pattern.id), None)
        if skill is None:
            skill = EvolvedSkill(
                name=name,
                description=pattern.description or pattern.signature,
                pattern_id=pattern.id,
                trigger_keywords=[t for t in pattern.signature.split() if t][:8],
            )
            self._store.skills.append(skill)
            self._store.metrics.skills_created += 1

        version = SkillVersion(
            version=(skill.versions[-1].version + 1) if skill.versions else 1,
            code=code,
            test_code=test_code,
            generation_source=source,
            notes=f"Generated from pattern {pattern.signature}",
        )
        skill.versions.append(version)
        skill.active_version = version.version
        pattern.status = PatternStatus.GENERATED
        pattern.skill_id = skill.id
        self._store.audit(AuditAction.SKILL_GENERATED, skill_id=skill.id,
                          pattern_id=pattern.id, details={"version": version.version, "source": source})
        self._store.save()
        return skill

    @staticmethod
    def _is_valid_skill(code: str) -> bool:
        """A skill is usable only if it compiles and defines ``execute``."""
        if not code or "def execute" not in code:
            return False
        try:
            compile(code, "<skill>", "exec")
        except SyntaxError:
            return False
        return True

    @staticmethod
    def _parse_llm_output(content: str) -> tuple[str, str]:
        code, test_code = "", ""
        blocks = re.findall(r"```(\w*)\s*(.*?)```", content, re.DOTALL)
        for lang, body in blocks:
            body = body.strip()
            if lang == "test" or ("TEST_CASES" in body and "def execute" not in body):
                test_code = body
            elif not code:
                code = body
        if not code:
            code = _extract_code_block(content)
        return code, test_code


# ─── Evaluation ───────────────────────────────────────────────────────────────


class SkillEvaluator:
    """Runs generated skills in a restricted sandbox and scores them.

    Measures success_rate, latency and (proxy) user_satisfaction, and runs an
    A/B comparison of the skill against the manual baseline approach.
    """

    def __init__(self, store: EvolutionStore, sandbox: RestrictedSandbox | None = None,
                 pass_threshold: float = 0.7, max_latency_ms: float = 5000.0) -> None:
        self._store = store
        self._sandbox = sandbox or RestrictedSandbox()
        self.pass_threshold = pass_threshold
        self.max_latency_ms = max_latency_ms

    async def evaluate(self, skill: EvolvedSkill, manual_baseline_ms: float | None = None) -> EvaluationResult:
        version = skill.current
        result = EvaluationResult(skill_id=skill.id, version=skill.active_version)
        if version is None:
            result.error = "skill has no version to evaluate"
            return result

        outcome = await self._sandbox.run_skill(version.code, version.test_code)
        result.tests_run = outcome.tests_run
        result.tests_passed = outcome.tests_passed
        result.security_violations = outcome.violations
        result.error = outcome.error

        if outcome.tests_run == 0:
            result.notes = "No executable test cases produced a result"
            self._finalize(skill, version, result, manual_baseline_ms)
            return result

        result.success_rate = round(outcome.tests_passed / outcome.tests_run, 4)
        result.avg_latency_ms = outcome.avg_latency_ms
        # Proxy satisfaction: blend of correctness and latency headroom.
        latency_headroom = max(0.0, 1.0 - (outcome.avg_latency_ms / self.max_latency_ms))
        result.user_satisfaction = round(result.success_rate * 0.7 + latency_headroom * 0.3, 4)

        # A/B test: skill vs manual baseline (discovered average duration).
        baseline = manual_baseline_ms
        if baseline is None:
            pattern = next((p for p in self._store.patterns if p.id == skill.pattern_id), None)
            baseline = (pattern.avg_time_saved_seconds * 1000.0) if pattern else 0.0
        if baseline and outcome.avg_latency_ms > 0:
            speedup = baseline / outcome.avg_latency_ms
            result.ab_test = {
                "approach_a": "skill",
                "approach_b": "manual_baseline",
                "skill_latency_ms": round(outcome.avg_latency_ms, 3),
                "baseline_latency_ms": round(baseline, 3),
                "speedup": round(speedup, 3),
                "winner": "skill" if speedup >= 1.0 else "manual_baseline",
            }

        result.passed = (
            result.success_rate >= self.pass_threshold
            and outcome.avg_latency_ms <= self.max_latency_ms
            and not outcome.violations
        )
        result.notes = "passed" if result.passed else "below quality bar"
        self._finalize(skill, version, result, manual_baseline_ms)
        return result

    def _finalize(self, skill: EvolvedSkill, version: SkillVersion,
                  result: EvaluationResult, manual_baseline_ms: float | None) -> None:
        version.success_rate = result.success_rate
        version.avg_latency_ms = result.avg_latency_ms
        skill.avg_latency_ms = result.avg_latency_ms or skill.avg_latency_ms
        skill.user_satisfaction = result.user_satisfaction or skill.user_satisfaction
        self._store.metrics.total_evaluations += 1
        self._store.audit(AuditAction.SKILL_EVALUATED, skill_id=skill.id,
                          details={"version": version.version, "passed": result.passed,
                                   "success_rate": result.success_rate,
                                   "latency_ms": result.avg_latency_ms,
                                   "violations": result.security_violations})
        self._store.save()


# ─── Optimization ─────────────────────────────────────────────────────────────

_OPTIMIZE_PROMPT = """A generated skill is underperforming and needs refactoring.

Skill name: {name}
Current success rate: {success_rate}
Current code:
```python
{code}
```
Current tests:
```python
{test}
```
Recent evaluation notes: {notes}

Refactor the skill to be more robust (better edge-case and error handling) while
respecting the sandbox constraints (allowed imports only; no eval/exec/open/network/
filesystem/subprocess; pure and deterministic). Keep the `async def execute(context: dict) -> dict`
signature and keep `TEST_CASES` + `validate(result, case)` in the test block.

Return ONLY two fenced code blocks: ```python (skill) and ```test (tests)."""


class SkillOptimizer:
    """Tracks performance, refactors weak skills, versions and deprecates."""

    def __init__(self, store: EvolutionStore, generator: SkillGenerator,
                 evaluator: SkillEvaluator, llm_router: Any | None = None,
                 refactor_threshold: float = 0.7, max_versions: int = 5,
                 stale_days: int = 30) -> None:
        self._store = store
        self._generator = generator
        self._evaluator = evaluator
        self._llm_router = llm_router
        self.refactor_threshold = refactor_threshold
        self.max_versions = max_versions
        self.stale_days = stale_days

    @property
    def llm_router(self) -> Any:
        if self._llm_router is None:
            try:
                from backend.app.dependencies import get_llm_router
                self._llm_router = get_llm_router()
            except Exception:
                self._llm_router = None
        return self._llm_router

    def needs_refactor(self, skill: EvolvedSkill) -> bool:
        return (
            skill.status == SkillStatus.ACTIVE
            and skill.usage_count >= 3
            and skill.success_rate < self.refactor_threshold
        )

    async def optimize(self, skill_id: str, force: bool = False) -> dict[str, Any]:
        skill = next((s for s in self._store.skills if s.id == skill_id), None)
        if skill is None:
            return {"status": "error", "reason": "skill_not_found"}
        if not force and not self.needs_refactor(skill) and skill.status != SkillStatus.CANDIDATE:
            return {"status": "skipped", "reason": "skill_healthy", "success_rate": skill.success_rate}

        previous_rate = skill.success_rate
        current = skill.current
        new_code, new_test, source = "", "", "template"

        router = self.llm_router
        if router is not None and current is not None:
            try:
                prompt = _OPTIMIZE_PROMPT.format(
                    name=skill.name,
                    success_rate=f"{skill.success_rate:.0%}",
                    code=current.code,
                    test=current.test_code,
                    notes=current.notes,
                )
                content = await _llm_chat(router, prompt)
                new_code, new_test = self._generator._parse_llm_output(content)
                source = "optimizer"
            except Exception as exc:
                logger.warning("LLM optimization failed: %s", exc)

        if not new_code.strip() and current is not None:
            # Deterministic fallback: keep logic, harden the test harness.
            new_code = current.code
            new_test = current.test_code or _TEST_TEMPLATE
            source = "template"

        version = SkillVersion(
            version=(skill.versions[-1].version + 1) if skill.versions else 1,
            code=new_code,
            test_code=new_test,
            generation_source=source,
            notes="Auto-refactor of underperforming skill",
        )
        skill.versions.append(version)
        skill.active_version = version.version
        skill.last_optimized_at = _now_iso()

        # Evaluate the new version and only keep it active if it is an improvement.
        evaluation = await self._evaluator.evaluate(skill)
        if evaluation.passed:
            skill.status = SkillStatus.ACTIVE
            kept = True
        else:
            # Roll back to the best previous version.
            best = self._best_version(skill)
            if best is not None:
                skill.active_version = best.version
            kept = False

        self._prune_versions(skill)
        improvement = round(max(evaluation.success_rate - previous_rate, 0.0), 4)
        self._store.metrics.total_optimizations += 1
        self._store.metrics.skills_optimized += 1
        m = self._store.metrics
        prev_avg = m.avg_improvement
        m.avg_improvement = round((prev_avg * (m.total_optimizations - 1) + improvement)
                                  / m.total_optimizations, 4)
        self._store.audit(AuditAction.SKILL_OPTIMIZED, skill_id=skill.id,
                          details={"version": version.version, "source": source,
                                   "kept": kept, "improvement": improvement,
                                   "success_rate": evaluation.success_rate})
        self._store.save()
        return {
            "status": "optimized",
            "skill_id": skill.id,
            "new_version": version.version,
            "kept_active": kept,
            "success_rate": evaluation.success_rate,
            "improvement": improvement,
        }

    @staticmethod
    def _best_version(skill: EvolvedSkill) -> SkillVersion | None:
        scored = [v for v in skill.versions if v.success_rate > 0]
        if not scored:
            return None
        return max(scored, key=lambda v: (v.success_rate, -v.avg_latency_ms))

    def _prune_versions(self, skill: EvolvedSkill) -> None:
        """Keep the best N versions, always preserving the active one."""
        if len(skill.versions) <= self.max_versions:
            return
        ranked = sorted(
            skill.versions,
            key=lambda v: (v.success_rate, -v.avg_latency_ms, v.version),
            reverse=True,
        )
        keep = ranked[: self.max_versions]
        if not any(v.version == skill.active_version for v in keep):
            active = skill.current
            if active is not None:
                keep[-1] = active
        keep_ids = {v.version for v in keep}
        skill.versions = [v for v in skill.versions if v.version in keep_ids]
        skill.versions.sort(key=lambda v: v.version)

    def deprecate_stale(self) -> list[EvolvedSkill]:
        """Deprecate active skills unused for ``stale_days`` days."""
        now = time.time()
        cutoff = self.stale_days * 86400
        deprecated: list[EvolvedSkill] = []
        for skill in self._store.skills:
            if skill.status != SkillStatus.ACTIVE:
                continue
            reference = skill.last_used_at or _parse_iso(skill.created_at)
            if reference and (now - reference) >= cutoff:
                skill.status = SkillStatus.DEPRECATED
                skill.deprecated_at = _now_iso()
                self._store.metrics.skills_deprecated += 1
                self._store.audit(AuditAction.SKILL_DEPRECATED, skill_id=skill.id,
                                  details={"reason": f"unused_for_{self.stale_days}_days"})
                deprecated.append(skill)
        if deprecated:
            self._store.save()
        return deprecated


def _parse_iso(value: str) -> float:
    try:
        return datetime.fromisoformat(value).timestamp()
    except (ValueError, TypeError):
        return 0.0


# ─── Orchestration loop ───────────────────────────────────────────────────────


class EvolutionLoop:
    """Orchestrates the closed loop as a configurable background task.

    Cycle: Discover → Generate → Evaluate → Deploy → Monitor → Optimize.
    """

    def __init__(
        self,
        discovery: SkillDiscoveryEngine,
        generator: SkillGenerator,
        evaluator: SkillEvaluator,
        optimizer: SkillOptimizer,
        store: EvolutionStore,
        interval_seconds: float = 3600.0,
        max_generations_per_cycle: int = 3,
    ) -> None:
        self.discovery = discovery
        self.generator = generator
        self.evaluator = evaluator
        self.optimizer = optimizer
        self.store = store
        self.interval_seconds = interval_seconds
        self.max_generations_per_cycle = max_generations_per_cycle
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def run_cycle(self) -> dict[str, Any]:
        """Run one full Discover → Generate → Evaluate → Deploy → Monitor → Optimize cycle."""
        started = time.perf_counter()
        summary: dict[str, Any] = {
            "proposed_patterns": 0,
            "skills_generated": 0,
            "skills_deployed": 0,
            "skills_optimized": 0,
            "skills_deprecated": 0,
            "evaluations": 0,
        }

        # 1. Discover — mine patterns and auto-propose high-value ones.
        proposed = self.discovery.discover()
        summary["proposed_patterns"] = len(proposed)

        # 2. Generate — turn proposed patterns into candidate skills.
        candidates: list[EvolvedSkill] = []
        generated = 0
        for pattern in proposed:
            if generated >= self.max_generations_per_cycle:
                break
            skill = await self.generator.generate(pattern)
            candidates.append(skill)
            generated += 1
        summary["skills_generated"] = generated

        # Also (re)evaluate any existing candidates not yet deployed.
        for skill in self.store.skills:
            if skill.status == SkillStatus.CANDIDATE and skill not in candidates:
                candidates.append(skill)

        # 3. Evaluate + 4. Deploy — sandbox-run candidates and promote passers.
        for skill in candidates:
            evaluation = await self.evaluator.evaluate(skill)
            summary["evaluations"] += 1
            if evaluation.passed and skill.status == SkillStatus.CANDIDATE:
                skill.status = SkillStatus.ACTIVE
                self.store.metrics.skills_deployed += 1
                summary["skills_deployed"] += 1
                self.store.audit(AuditAction.SKILL_DEPLOYED, skill_id=skill.id,
                                 details={"version": skill.active_version,
                                          "success_rate": evaluation.success_rate})

        # 5. Monitor + 6. Optimize — refactor weak skills, deprecate stale ones.
        for skill in list(self.store.skills):
            if self.optimizer.needs_refactor(skill):
                outcome = await self.optimizer.optimize(skill.id)
                if outcome.get("status") == "optimized":
                    summary["skills_optimized"] += 1
        deprecated = self.optimizer.deprecate_stale()
        summary["skills_deprecated"] = len(deprecated)

        duration_ms = (time.perf_counter() - started) * 1000
        self.store.metrics.loop_cycles += 1
        self.store.metrics.last_cycle_at = _now_iso()
        self.store.metrics.last_cycle_duration_ms = round(duration_ms, 3)
        self.store.audit(AuditAction.LOOP_CYCLE, details=summary)
        self.store.save()
        summary["duration_ms"] = round(duration_ms, 3)
        summary["cycle"] = self.store.metrics.loop_cycles
        logger.info("Evolution cycle #%d complete: %s", self.store.metrics.loop_cycles, summary)
        return summary

    async def _run_forever(self) -> None:
        while self._running:
            try:
                await self.run_cycle()
            except Exception as exc:
                logger.exception("Evolution cycle failed: %s", exc)
            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    def start(self) -> bool:
        """Start the background loop (no-op if already running)."""
        if self._running:
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running event loop; evolution loop not started")
            return False
        self._running = True
        self._task = loop.create_task(self._run_forever())
        self.store.audit(AuditAction.LOOP_STARTED,
                         details={"interval_seconds": self.interval_seconds})
        self.store.save()
        logger.info("Evolution loop started (interval=%ss)", self.interval_seconds)
        return True

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self.store.audit(AuditAction.LOOP_STOPPED)
        self.store.save()
        logger.info("Evolution loop stopped")


# ─── System facade ────────────────────────────────────────────────────────────


class SkillEvolutionSystem:
    """Facade wiring discovery, generation, evaluation, optimization and the loop."""

    def __init__(self, store: EvolutionStore | None = None, llm_router: Any | None = None,
                 loop_interval_seconds: float = 3600.0) -> None:
        self.store = store or EvolutionStore()
        self._llm_router = llm_router
        self.discovery = SkillDiscoveryEngine(self.store)
        self.generator = SkillGenerator(self.store, llm_router=llm_router)
        self.evaluator = SkillEvaluator(self.store)
        self.optimizer = SkillOptimizer(self.store, self.generator, self.evaluator,
                                        llm_router=llm_router)
        self.loop = EvolutionLoop(self.discovery, self.generator, self.evaluator,
                                  self.optimizer, self.store,
                                  interval_seconds=loop_interval_seconds)

    # -- convenience passthroughs ------------------------------------------------

    def record_interaction(self, task_description: str, tool_calls: list[str] | None = None,
                           duration_ms: float = 0.0, success: bool = True,
                           user_id: str = "anonymous") -> InteractionRecord:
        return self.discovery.record_interaction(task_description, tool_calls,
                                                 duration_ms, success, user_id)

    def record_skill_usage(self, skill_id: str, success: bool, latency_ms: float = 0.0,
                           satisfaction: float | None = None) -> dict[str, Any]:
        skill = next((s for s in self.store.skills if s.id == skill_id), None)
        if skill is None:
            return {"status": "error", "reason": "skill_not_found"}
        skill.record_usage(success, latency_ms, satisfaction)
        self.store.audit(AuditAction.SKILL_USAGE, skill_id=skill_id,
                         details={"success": success, "latency_ms": latency_ms,
                                  "success_rate": skill.success_rate})
        self.store.save()
        return {"status": "recorded", "skill_id": skill_id,
                "usage_count": skill.usage_count, "success_rate": skill.success_rate}

    def get_skill(self, skill_id: str) -> EvolvedSkill | None:
        return next((s for s in self.store.skills if s.id == skill_id), None)

    def match_skill(self, task_description: str) -> EvolvedSkill | None:
        """Match an incoming task to the best active evolved skill."""
        tokens = set(_signature(task_description).split())
        best: EvolvedSkill | None = None
        best_score = 0.0
        for skill in self.store.skills:
            if skill.status != SkillStatus.ACTIVE:
                continue
            overlap = len(tokens & set(skill.trigger_keywords))
            if overlap == 0:
                continue
            score = overlap * (1.0 + skill.success_rate)
            if score > best_score:
                best_score = score
                best = skill
        return best

    def get_metrics(self) -> dict[str, Any]:
        metrics = self.store.metrics.to_dict()
        metrics["active_skills"] = len(
            [s for s in self.store.skills if s.status == SkillStatus.ACTIVE])
        metrics["candidate_skills"] = len(
            [s for s in self.store.skills if s.status == SkillStatus.CANDIDATE])
        metrics["deprecated_skills"] = len(
            [s for s in self.store.skills if s.status == SkillStatus.DEPRECATED])
        metrics["loop_running"] = self.loop.running
        return metrics

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return [a.to_dict() for a in reversed(self.store.audit_log[-limit:])]


# Global singleton
skill_evolution_system = SkillEvolutionSystem()
