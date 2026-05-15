"""L2 phase memory: SQLite KV store with namespacing.

Use for "what has this phase already figured out": decisions, skipped files,
known-bad fixtures, blockers needing human review. Cheap to read, cheap to
write, survives across sessions.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    ns         TEXT NOT NULL,
    key        TEXT NOT NULL,
    value_json TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (ns, key)
);
"""


class PhaseMemory:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    def put(self, ns: str, key: str, value: Any) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO kv(ns, key, value_json, updated_at) VALUES (?, ?, ?, ?)",
            (ns, key, json.dumps(value, ensure_ascii=False), time.time()),
        )

    def get(self, ns: str, key: str, default: Any = None) -> Any:
        cur = self._conn.execute(
            "SELECT value_json FROM kv WHERE ns = ? AND key = ?", (ns, key)
        )
        row = cur.fetchone()
        return json.loads(row[0]) if row else default

    def list_keys(self, ns: str) -> list[str]:
        cur = self._conn.execute("SELECT key FROM kv WHERE ns = ? ORDER BY key", (ns,))
        return [r[0] for r in cur.fetchall()]

    def delete(self, ns: str, key: str) -> None:
        self._conn.execute("DELETE FROM kv WHERE ns = ? AND key = ?", (ns, key))

    def close(self) -> None:
        self._conn.close()
