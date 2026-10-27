"""Local SQLite: consent/enrollment state and the outbox of not-yet-sent metadata."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


class TelemetryStore:
    def __init__(self, directory: Path, outbox_max: int = 5000):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "telemetry.db"
        self.outbox_max = outbox_max
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outbox (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK (kind IN ('event','error')),
                    payload TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # -- state ------------------------------------------------------------------
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._conn() as c:
            row = c.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def flag(self, key: str) -> bool:
        return self.get(key) == "1"

    def set_flag(self, key: str, value: bool) -> None:
        self.set(key, "1" if value else "0")

    # -- authorization lease ---------------------------------------------------
    def save_lease(self, status: str, lease_expires_at: float, details: Optional[Dict[str, Any]] = None) -> None:
        payload = json.dumps({"status": status, "lease_expires_at": lease_expires_at, "details": details or {}})
        self.set("auth_lease", payload)

    def get_lease(self) -> Dict[str, Any]:
        raw = self.get("auth_lease")
        if not raw:
            return {"status": "ACTIVE", "lease_expires_at": 0.0, "details": {}}
        try:
            return json.loads(raw)
        except Exception:
            return {"status": "ACTIVE", "lease_expires_at": 0.0, "details": {}}

    def invalidate_lease(self, status: str = "REVOKED", reason: str = "Revoked by Central") -> None:
        self.save_lease(status, 0.0, {"reason": reason})

    # -- outbox -----------------------------------------------------------------
    def enqueue(self, kind: str, payload: Dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO outbox(kind,payload) VALUES(?,?)", (kind, json.dumps(payload, separators=(",", ":"))))
            c.execute("DELETE FROM outbox WHERE seq <= (SELECT MAX(seq) FROM outbox) - ?", (self.outbox_max,))  # bounded

    def peek(self, kind: str, limit: int) -> List[Tuple[int, Dict[str, Any]]]:
        with self._conn() as c:
            rows = c.execute("SELECT seq,payload FROM outbox WHERE kind=? ORDER BY seq LIMIT ?", (kind, limit)).fetchall()
        return [(seq, json.loads(p)) for seq, p in rows]

    def delete(self, seqs: List[int]) -> None:
        if seqs:
            with self._conn() as c:
                c.executemany("DELETE FROM outbox WHERE seq=?", [(s,) for s in seqs])

    def size(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    def purge_outbox(self) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM outbox")
