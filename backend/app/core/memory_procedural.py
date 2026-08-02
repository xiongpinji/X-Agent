"""Procedural Memory — Hermes-Agent-style five-layer memory (Layer: Procedural).

Stores *how-to* knowledge extracted from successful task completions in the
form::

    trigger_condition  ->  action_sequence  ->  expected_outcome

Procedures are auto-extracted from repeated successful patterns and can be
matched against the current task context for *fast-path* execution.  Matching
is performed against an in-memory index so it completes well under 10ms, while
persistence to disk is handled via SQLite (``aiosqlite``).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

DEFAULT_PROCEDURAL_DB_PATH = Path("data/memory_procedural.db")

# Number of times a pattern must succeed before it is distilled into a procedure
DEFAULT_EXTRACTION_THRESHOLD = 3


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    """Lowercase token set used for both indexing and matching."""
    return {t.lower() for t in _TOKEN_RE.findall(text)}


@dataclass
class ProcedureRecord:
    """A stored procedure (how-to knowledge)."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    trigger_pattern: str = ""
    steps: list[str] = field(default_factory=list)
    expected_outcome: str = ""
    success_count: int = 0
    failure_count: int = 0
    last_used: datetime | None = None
    avg_time_saved: float = 0.0  # seconds
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    @property
    def reliability(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["last_used"] = _iso(self.last_used) if self.last_used else None
        data["created_at"] = _iso(self.created_at)
        data["updated_at"] = _iso(self.updated_at)
        return data

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ProcedureRecord:
        def _parse_dt(val: Any) -> datetime | None:
            if isinstance(val, datetime):
                return val
            if isinstance(val, str) and val:
                try:
                    return datetime.fromisoformat(val)
                except ValueError:
                    return None
            return None

        def _load_list(raw: Any) -> list[str]:
            if isinstance(raw, list):
                return [str(x) for x in raw]
            if isinstance(raw, str) and raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed]
                except json.JSONDecodeError:
                    pass
            return []

        return cls(
            id=str(row.get("id") or str(uuid4())),
            name=str(row.get("name") or ""),
            trigger_pattern=str(row.get("trigger_pattern") or ""),
            steps=_load_list(row.get("steps")),
            expected_outcome=str(row.get("expected_outcome") or ""),
            success_count=int(row.get("success_count") or 0),
            failure_count=int(row.get("failure_count") or 0),
            last_used=_parse_dt(row.get("last_used")),
            avg_time_saved=float(row.get("avg_time_saved") or 0.0),
            tags=_load_list(row.get("tags")),
            created_at=_parse_dt(row.get("created_at")) or _utcnow(),
            updated_at=_parse_dt(row.get("updated_at")) or _utcnow(),
        )


@dataclass
class ProcedureMatch:
    """Result of matching a context against stored procedures."""

    procedure: ProcedureRecord
    score: float
    matched_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "procedure": self.procedure.to_dict(),
            "score": round(self.score, 4),
            "matched_terms": self.matched_terms,
            "reliability": round(self.procedure.reliability, 4),
        }


class ProcedureMatcher:
    """Fuzzy matching of the current context against stored procedures.

    Performance strategy (matches hundreds of procedures in well under 10ms):

    1. Candidate gathering via a prebuilt inverted index (token -> proc ids),
       so only procedures sharing at least one token are considered.
    2. A cheap token-coverage first pass over those candidates.
    3. An expensive ``SequenceMatcher`` fuzzy refinement applied only to the
       top ``fuzzy_refine_top`` candidates.
    """

    def __init__(
        self,
        token_weight: float = 0.7,
        sequence_weight: float = 0.3,
        fuzzy_refine_top: int = 20,
    ) -> None:
        self.token_weight = token_weight
        self.sequence_weight = sequence_weight
        self.fuzzy_refine_top = fuzzy_refine_top

    def match(
        self,
        context: str,
        procedures: list[ProcedureRecord],
        *,
        top_k: int = 5,
        threshold: float = 0.15,
        token_index: dict[str, set[str]] | None = None,
        proc_tokens: dict[str, frozenset[str]] | None = None,
    ) -> list[ProcedureMatch]:
        """Return procedures matching ``context`` sorted by descending score."""
        if not context.strip() or not procedures:
            return []

        context_tokens = _tokenize(context)
        if not context_tokens:
            return []

        by_id = {p.id: p for p in procedures}

        # 1) Fast candidate gathering via the inverted index.
        if token_index is not None:
            candidate_ids: set[str] = set()
            for tok in context_tokens:
                bucket = token_index.get(tok)
                if bucket:
                    candidate_ids |= bucket
        else:
            candidate_ids = set(by_id.keys())

        if not candidate_ids:
            return []

        # 2) Cheap token-coverage first pass.
        first_pass: list[tuple[float, float, ProcedureRecord, set[str]]] = []
        for pid in candidate_ids:
            proc = by_id.get(pid)
            if proc is None:
                continue
            ptokens = (proc_tokens or {}).get(pid)
            if ptokens is None:
                ptokens = frozenset(_tokenize(proc.trigger_pattern))
            if not ptokens:
                continue
            overlap = context_tokens & ptokens
            coverage = len(overlap) / len(ptokens)
            token_score = self.token_weight * coverage + 0.05 * proc.reliability
            if token_score > 0:
                first_pass.append((token_score, coverage, proc, overlap))

        if not first_pass:
            return []

        first_pass.sort(key=lambda x: x[0], reverse=True)

        # 3) Fuzzy refinement on the top candidates only.
        context_lower = context.lower()
        refine_n = min(self.fuzzy_refine_top, len(first_pass))
        results: list[ProcedureMatch] = []
        for idx, (token_score, coverage, proc, overlap) in enumerate(first_pass):
            if idx < refine_n and self.sequence_weight > 0:
                seq_ratio = SequenceMatcher(
                    None, context_lower, proc.trigger_pattern.lower()
                ).ratio()
                final = (
                    self.token_weight * coverage
                    + self.sequence_weight * seq_ratio
                    + 0.05 * proc.reliability
                )
            else:
                final = token_score
            final = min(final, 1.0)
            if final >= threshold:
                results.append(
                    ProcedureMatch(
                        procedure=proc,
                        score=final,
                        matched_terms=sorted(overlap),
                    )
                )

        results.sort(key=lambda m: m.score, reverse=True)
        return results[:top_k]


class ProceduralMemory:
    """Async procedural memory with disk persistence and fast in-memory matching."""

    def __init__(
        self,
        db_path: Path | str = DEFAULT_PROCEDURAL_DB_PATH,
        matcher: ProcedureMatcher | None = None,
        extraction_threshold: int = DEFAULT_EXTRACTION_THRESHOLD,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.matcher = matcher or ProcedureMatcher()
        self.extraction_threshold = extraction_threshold

        # In-memory index for <10ms matching
        self._procedures: dict[str, ProcedureRecord] = {}
        # Inverted index: token -> set of procedure ids (for fast candidate gathering)
        self._token_index: dict[str, set[str]] = {}
        # Per-procedure token cache: procedure id -> frozenset of trigger tokens
        self._proc_tokens: dict[str, frozenset[str]] = {}
        # Tracks repeated successful patterns: signature -> count/metadata
        self._pattern_tracker: dict[str, dict[str, Any]] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _connect(self) -> Any:
        import aiosqlite

        conn = await aiosqlite.connect(self.db_path, timeout=30.0)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def initialize(self) -> None:
        if self._loaded:
            return
        conn = await self._connect()
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS procedures (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    trigger_pattern TEXT,
                    steps TEXT,
                    expected_outcome TEXT,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    avg_time_saved REAL DEFAULT 0.0,
                    tags TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM procedures")
            rows = await cursor.fetchall()
            for row in rows:
                proc = ProcedureRecord.from_row(dict(row))
                self._procedures[proc.id] = proc
                self._index_procedure(proc)
            self._loaded = True
            logger.info("ProceduralMemory loaded %d procedures", len(self._procedures))
        finally:
            await conn.close()

    async def _persist(self, proc: ProcedureRecord) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                """
                INSERT OR REPLACE INTO procedures (
                    id, name, trigger_pattern, steps, expected_outcome,
                    success_count, failure_count, last_used, avg_time_saved,
                    tags, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proc.id,
                    proc.name,
                    proc.trigger_pattern,
                    json.dumps(proc.steps, ensure_ascii=False),
                    proc.expected_outcome,
                    proc.success_count,
                    proc.failure_count,
                    _iso(proc.last_used) if proc.last_used else None,
                    proc.avg_time_saved,
                    json.dumps(proc.tags, ensure_ascii=False),
                    _iso(proc.created_at),
                    _iso(proc.updated_at),
                ),
            )
            await conn.commit()
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def store_procedure(
        self,
        name: str,
        trigger_pattern: str,
        steps: list[str],
        *,
        expected_outcome: str = "",
        tags: list[str] | None = None,
        success_count: int = 1,
    ) -> ProcedureRecord:
        """Explicitly store a procedure."""
        await self.initialize()
        proc = ProcedureRecord(
            name=name,
            trigger_pattern=trigger_pattern,
            steps=steps,
            expected_outcome=expected_outcome,
            tags=tags or [],
            success_count=success_count,
        )
        self._procedures[proc.id] = proc
        self._index_procedure(proc)
        await self._persist(proc)
        logger.info("Procedure stored: %s (%s)", proc.id, name)
        return proc

    async def record_success(
        self,
        trigger_pattern: str,
        steps: list[str],
        *,
        expected_outcome: str = "",
        time_taken: float = 0.0,
        tags: list[str] | None = None,
    ) -> ProcedureRecord | None:
        """Record a successful task completion.

        When the same trigger/steps pattern succeeds ``extraction_threshold``
        times, a procedure is auto-extracted (or reinforced if it already
        exists).  Returns the affected procedure, if any.
        """
        await self.initialize()
        signature = self._signature(trigger_pattern, steps)
        entry = self._pattern_tracker.get(signature)
        if entry is None:
            entry = {
                "count": 0,
                "trigger_pattern": trigger_pattern,
                "steps": steps,
                "expected_outcome": expected_outcome,
                "tags": tags or [],
                "times": [],
                "procedure_id": None,
            }
            self._pattern_tracker[signature] = entry

        entry["count"] += 1
        if time_taken > 0:
            entry["times"].append(time_taken)

        # Reinforce existing procedure if already extracted
        if entry["procedure_id"] and entry["procedure_id"] in self._procedures:
            proc = self._procedures[entry["procedure_id"]]
            proc.success_count += 1
            proc.last_used = _utcnow()
            proc.updated_at = _utcnow()
            proc.avg_time_saved = self._avg(entry["times"])
            await self._persist(proc)
            return proc

        # Auto-extract once threshold reached
        if entry["count"] >= self.extraction_threshold:
            name = self._derive_name(trigger_pattern)
            proc = ProcedureRecord(
                name=name,
                trigger_pattern=trigger_pattern,
                steps=steps,
                expected_outcome=expected_outcome,
                tags=entry["tags"],
                success_count=entry["count"],
                last_used=_utcnow(),
                avg_time_saved=self._avg(entry["times"]),
            )
            self._procedures[proc.id] = proc
            self._index_procedure(proc)
            entry["procedure_id"] = proc.id
            await self._persist(proc)
            logger.info(
                "Auto-extracted procedure %s from %d successes", proc.id, entry["count"]
            )
            return proc

        return None

    async def record_failure(self, procedure_id: str) -> None:
        """Record a failed application of a procedure (lowers reliability)."""
        await self.initialize()
        proc = self._procedures.get(procedure_id)
        if proc is None:
            return
        proc.failure_count += 1
        proc.updated_at = _utcnow()
        await self._persist(proc)

    # ------------------------------------------------------------------
    # Read / match
    # ------------------------------------------------------------------

    async def list_procedures(self, *, limit: int = 100) -> list[ProcedureRecord]:
        await self.initialize()
        procs = list(self._procedures.values())
        procs.sort(key=lambda p: (p.success_count, p.reliability), reverse=True)
        return procs[:limit]

    async def get_procedure(self, procedure_id: str) -> ProcedureRecord | None:
        await self.initialize()
        return self._procedures.get(procedure_id)

    async def match_context(
        self,
        context: str,
        *,
        top_k: int = 5,
        threshold: float = 0.15,
    ) -> list[ProcedureMatch]:
        """Match the current task context against stored procedures (fast-path)."""
        await self.initialize()
        started = time.perf_counter()
        matches = self.matcher.match(
            context,
            list(self._procedures.values()),
            top_k=top_k,
            threshold=threshold,
            token_index=self._token_index,
            proc_tokens=self._proc_tokens,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.debug("Procedure match over %d procedures took %.2fms", len(self._procedures), elapsed_ms)
        return matches

    async def mark_used(self, procedure_id: str, *, time_saved: float = 0.0) -> None:
        """Mark a procedure as used (updates last_used and avg_time_saved)."""
        await self.initialize()
        proc = self._procedures.get(procedure_id)
        if proc is None:
            return
        proc.last_used = _utcnow()
        if time_saved > 0:
            # Running average
            n = proc.success_count or 1
            proc.avg_time_saved = ((proc.avg_time_saved * (n - 1)) + time_saved) / n
        await self._persist(proc)

    async def delete_procedure(self, procedure_id: str) -> bool:
        await self.initialize()
        if procedure_id not in self._procedures:
            return False
        del self._procedures[procedure_id]
        self._unindex_procedure(procedure_id)
        conn = await self._connect()
        try:
            await conn.execute("DELETE FROM procedures WHERE id = ?", (procedure_id,))
            await conn.commit()
        finally:
            await conn.close()
        return True

    async def get_stats(self) -> dict[str, Any]:
        await self.initialize()
        total = len(self._procedures)
        total_success = sum(p.success_count for p in self._procedures.values())
        avg_reliability = (
            sum(p.reliability for p in self._procedures.values()) / total if total else 0.0
        )
        return {
            "total_procedures": total,
            "total_successes": total_success,
            "avg_reliability": round(avg_reliability, 4),
            "tracked_patterns": len(self._pattern_tracker),
            "extraction_threshold": self.extraction_threshold,
            "db_path": str(self.db_path),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _index_procedure(self, proc: ProcedureRecord) -> None:
        """Add a procedure to the in-memory inverted index."""
        tokens = frozenset(_tokenize(proc.trigger_pattern))
        self._proc_tokens[proc.id] = tokens
        for tok in tokens:
            self._token_index.setdefault(tok, set()).add(proc.id)

    def _unindex_procedure(self, procedure_id: str) -> None:
        """Remove a procedure from the in-memory inverted index."""
        tokens = self._proc_tokens.pop(procedure_id, frozenset())
        for tok in tokens:
            bucket = self._token_index.get(tok)
            if bucket is not None:
                bucket.discard(procedure_id)
                if not bucket:
                    del self._token_index[tok]

    @staticmethod
    def _signature(trigger_pattern: str, steps: list[str]) -> str:
        norm_trigger = " ".join(trigger_pattern.lower().split())
        norm_steps = "|".join(" ".join(s.lower().split()) for s in steps)
        return f"{norm_trigger}##{norm_steps}"

    @staticmethod
    def _derive_name(trigger_pattern: str) -> str:
        words = re.findall(r"[\w\u4e00-\u9fff]+", trigger_pattern, re.UNICODE)
        if not words:
            return "procedure"
        return " ".join(words[:6])

    @staticmethod
    def _avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0


# Global instance (persisted to disk by default)
procedural_memory = ProceduralMemory()
