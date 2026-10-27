"""SQLite-backed session storage for Era Bridge's multi-turn conversations.

Structurally identical to Era Local Agent V2's session store -- kept
consistent deliberately so the same conversational pattern (pending
command, collected params, confirmed flag) is used at both layers.
This store is entirely Bridge-side; it has no relationship to
anything inside Era Local Agent.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from config import settings

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "era_bridge.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class SessionStore:
    def __init__(self, db_path: Path = DB_PATH, ttl_seconds: Optional[int] = None) -> None:
        self.db_path = db_path
        self.ttl_seconds = settings.SESSION_TTL_SECONDS if ttl_seconds is None else ttl_seconds
        self._init_db()
        self.prune_expired()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def new_session_id(self) -> str:
        return uuid.uuid4().hex

    def prune_expired(self) -> int:
        """Deletes sessions idle longer than the TTL. Returns rows removed."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM sessions WHERE updated_at < datetime('now', ?)", (f"-{int(self.ttl_seconds)} seconds",)
            )
            return cur.rowcount

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state FROM sessions WHERE session_id = ? AND updated_at >= datetime('now', ?)",
                (session_id, f"-{int(self.ttl_seconds)} seconds"),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            logger.warning("Corrupt session state for %s; discarding.", session_id)
            self.delete(session_id)
            return None

    def save(self, session_id: str, state: Dict[str, Any]) -> None:
        self.prune_expired()
        payload = json.dumps(state)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, state, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(session_id) DO UPDATE SET
                    state = excluded.state,
                    updated_at = excluded.updated_at
                """,
                (session_id, payload),
            )

    def delete(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
