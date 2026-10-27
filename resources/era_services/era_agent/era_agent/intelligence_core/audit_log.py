"""ERA Intelligence Core — Persistent Audit Log.

Thread-safe append-only JSONL audit trail for all ERA actions.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuditLog:
    """Append-only JSONL audit log. Thread-safe."""

    def __init__(self, log_path: str) -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(
        self,
        event_type: str,
        actor: str,
        payload: Dict[str, Any],
        risk_level: str = "low",
    ) -> str:
        """Write one audit event. Returns event_id."""
        event_id = uuid.uuid4().hex
        entry = {
            "id": event_id,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event_type": event_type,
            "actor": actor,
            "risk_level": risk_level,
            "payload": payload,
        }
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        return event_id

    def query(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return up to `limit` recent entries, optionally filtered by event_type."""
        entries = self._read_all()
        if event_type:
            entries = [e for e in entries if e.get("event_type") == event_type]
        return entries[-limit:]

    def get_recent(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Return events from the last N minutes."""
        cutoff = time.time() - (minutes * 60)
        result = []
        for e in self._read_all():
            try:
                ts = time.mktime(time.strptime(e["timestamp_utc"], "%Y-%m-%dT%H:%M:%SZ"))
                if ts >= cutoff:
                    result.append(e)
            except Exception:
                pass
        return result

    def _read_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._lock:
            text = self._path.read_text(encoding="utf-8")
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return entries
