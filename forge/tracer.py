"""SQLite-backed tracer for every LLM call and tool call.

Pillar 4 (Observability). The goal is end-to-end replay: given a run_id, we can
reconstruct every prompt, response, tool call, and outcome. Cost and latency
fall out naturally.

Design notes:
- One SQLite file per project (default .forge/trace.sqlite). Concurrent writers
  use WAL mode.
- Spans form a tree: a run contains agents, an agent contains LLM calls and
  tool calls, an LLM call may contain tool calls.
- Payloads (prompt, response) live in a separate blob table to keep span rows
  small; large bodies are gzipped.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS spans (
    span_id        TEXT PRIMARY KEY,
    parent_id      TEXT,
    run_id         TEXT NOT NULL,
    kind           TEXT NOT NULL,        -- run | agent | llm | tool
    name           TEXT NOT NULL,
    started_at     REAL NOT NULL,
    ended_at       REAL,
    status         TEXT,                 -- ok | error | cancelled
    model          TEXT,
    tokens_in      INTEGER,
    tokens_out     INTEGER,
    cache_read     INTEGER,
    cache_write    INTEGER,
    cost_usd       REAL,
    error_message  TEXT,
    attrs_json     TEXT
);
CREATE INDEX IF NOT EXISTS idx_spans_run     ON spans(run_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent  ON spans(parent_id);
CREATE INDEX IF NOT EXISTS idx_spans_kind    ON spans(kind);

CREATE TABLE IF NOT EXISTS payloads (
    span_id     TEXT NOT NULL,
    role        TEXT NOT NULL,            -- prompt | response | tool_input | tool_output
    body_gz     BLOB NOT NULL,
    PRIMARY KEY (span_id, role)
);
"""


@dataclass
class Span:
    span_id: str
    parent_id: str | None
    run_id: str
    kind: str
    name: str
    started_at: float
    ended_at: float | None = None
    status: str | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_read: int | None = None
    cache_write: int | None = None
    cost_usd: float | None = None
    error_message: str | None = None
    attrs: dict[str, Any] | None = None


class Tracer:
    """Append-only trace store.

    Not thread-safe at the Python level — use one Tracer per process/worker.
    SQLite WAL handles cross-process concurrency.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def span(
        self,
        kind: str,
        name: str,
        *,
        run_id: str,
        parent_id: str | None = None,
        attrs: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        s = Span(
            span_id=str(uuid.uuid4()),
            parent_id=parent_id,
            run_id=run_id,
            kind=kind,
            name=name,
            started_at=time.time(),
            attrs=attrs,
        )
        self._insert(s)
        try:
            yield s
            if s.status is None:
                s.status = "ok"
        except Exception as e:
            s.status = "error"
            s.error_message = f"{type(e).__name__}: {e}"
            raise
        finally:
            s.ended_at = time.time()
            self._update(s)

    def record_payload(self, span_id: str, role: str, body: str | bytes | dict) -> None:
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._conn.execute(
            "INSERT OR REPLACE INTO payloads(span_id, role, body_gz) VALUES (?, ?, ?)",
            (span_id, role, gzip.compress(body)),
        )

    def query_run(self, run_id: str) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM spans WHERE run_id = ? ORDER BY started_at", (run_id,)
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            """
            SELECT run_id,
                   MIN(started_at) AS started_at,
                   MAX(ended_at)   AS ended_at,
                   COUNT(*)        AS span_count,
                   SUM(cost_usd)   AS cost_usd,
                   SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS errors
            FROM spans
            GROUP BY run_id
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _insert(self, s: Span) -> None:
        self._conn.execute(
            """
            INSERT INTO spans(span_id, parent_id, run_id, kind, name, started_at, attrs_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                s.span_id,
                s.parent_id,
                s.run_id,
                s.kind,
                s.name,
                s.started_at,
                json.dumps(s.attrs) if s.attrs else None,
            ),
        )

    def _update(self, s: Span) -> None:
        self._conn.execute(
            """
            UPDATE spans
               SET ended_at=?, status=?, model=?, tokens_in=?, tokens_out=?,
                   cache_read=?, cache_write=?, cost_usd=?, error_message=?
             WHERE span_id=?
            """,
            (
                s.ended_at,
                s.status,
                s.model,
                s.tokens_in,
                s.tokens_out,
                s.cache_read,
                s.cache_write,
                s.cost_usd,
                s.error_message,
                s.span_id,
            ),
        )


def new_run_id() -> str:
    return str(uuid.uuid4())
