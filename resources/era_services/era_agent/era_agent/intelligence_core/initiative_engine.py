"""ERA Intelligence Core — Proactive Initiative Engine.

Scores potential suggestions using:
  relevance × importance × urgency × confidence − risk × intrusiveness

Only fires when score exceeds the threshold.  Never spams.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_COOLDOWN_SECONDS = 300          # 5-minute minimum between same-topic suggestions
_GLOBAL_COOLDOWN  = 60           # 1-minute minimum between ANY suggestion


@dataclass
class Initiative:
    id: str
    title: str
    message: str
    relevance: float
    importance: float
    urgency: float
    confidence: float
    risk: float
    intrusiveness: float
    score: float = 0.0
    created_at: float = field(default_factory=time.time)
    status: str = "suggested"   # suggested | dismissed | acted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "score": round(self.score, 3),
            "status": self.status,
            "created_at": self.created_at,
        }


class InitiativeEngine:
    """Generates proactive, non-spammy suggestions from context."""

    def __init__(self, score_threshold: float = 0.35) -> None:
        self.score_threshold = score_threshold
        self._last_by_topic: Dict[str, float] = {}
        self._last_global: float = 0.0
        self._history: List[Initiative] = []
        self._pending: List[Initiative] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, context: Dict[str, Any]) -> List[Initiative]:
        """Return new initiatives worth surfacing right now."""
        candidates = self._generate_candidates(context)
        fired: List[Initiative] = []

        now = time.time()
        if now - self._last_global < _GLOBAL_COOLDOWN:
            return []

        for c in sorted(candidates, key=lambda x: x.score, reverse=True):
            if c.score < self.score_threshold:
                continue
            topic = c.title
            last = self._last_by_topic.get(topic, 0.0)
            if now - last < _COOLDOWN_SECONDS:
                continue

            self._last_by_topic[topic] = now
            self._last_global = now
            c.status = "suggested"
            self._history.append(c)
            self._pending.append(c)
            fired.append(c)
            break  # surface at most one suggestion per evaluation cycle

        return fired

    def dismiss(self, initiative_id: str) -> bool:
        for init in self._pending:
            if init.id == initiative_id:
                init.status = "dismissed"
                self._pending.remove(init)
                return True
        return False

    def acted(self, initiative_id: str) -> bool:
        for init in self._pending:
            if init.id == initiative_id:
                init.status = "acted"
                self._pending.remove(init)
                return True
        return False

    def get_pending(self) -> List[Dict[str, Any]]:
        return [i.to_dict() for i in self._pending if i.status == "suggested"]

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [i.to_dict() for i in self._history[-limit:]]

    # ------------------------------------------------------------------
    # Candidate generation
    # ------------------------------------------------------------------

    def _score(self, relevance: float, importance: float, urgency: float,
               confidence: float, risk: float, intrusiveness: float) -> float:
        return relevance * importance * urgency * confidence - risk * intrusiveness

    def _make(self, title: str, message: str, **kw) -> Initiative:
        kw.setdefault("relevance", 0.8)
        kw.setdefault("importance", 0.8)
        kw.setdefault("urgency", 0.7)
        kw.setdefault("confidence", 0.9)
        kw.setdefault("risk", 0.05)
        kw.setdefault("intrusiveness", 0.3)
        score = self._score(
            kw["relevance"], kw["importance"], kw["urgency"],
            kw["confidence"], kw["risk"], kw["intrusiveness"],
        )
        return Initiative(
            id=uuid.uuid4().hex,
            title=title,
            message=message,
            score=score,
            **kw,
        )

    def _generate_candidates(self, context: Dict[str, Any]) -> List[Initiative]:
        candidates: List[Initiative] = []
        battery = context.get("battery") or {}
        cpu = context.get("cpu") or {}
        memory = context.get("memory") or {}
        disk = context.get("disk") or {}
        network = context.get("network") or {}
        activity = context.get("user_activity", "unknown")
        active_app = (context.get("active_app") or "").lower()
        observations: List[str] = context.get("observations", [])

        # Battery: critically low while working
        bat_pct = battery.get("percent")
        charging = battery.get("charging")
        if bat_pct is not None and bat_pct <= 15 and charging is False:
            urgency = 1.0 if bat_pct <= 10 else 0.85
            candidates.append(self._make(
                title="Low Battery Warning",
                message=f"Boss, your battery is at {bat_pct:.0f}% and the charger is disconnected. "
                        "Connect your charger to avoid interruption.",
                urgency=urgency,
                importance=0.95,
                intrusiveness=0.25,
            ))

        # High CPU while user is idle — possible runaway process
        cpu_pct = cpu.get("percent")
        if cpu_pct is not None and cpu_pct > 85 and activity == "idle":
            candidates.append(self._make(
                title="High CPU While Idle",
                message=f"CPU is at {cpu_pct:.0f}% but you appear idle. There may be a runaway process consuming resources.",
                urgency=0.7,
                importance=0.75,
                intrusiveness=0.35,
            ))

        # Memory pressure
        mem_pct = memory.get("percent")
        if mem_pct is not None and mem_pct > 90:
            candidates.append(self._make(
                title="Memory Pressure Critical",
                message=f"RAM usage is at {mem_pct:.0f}%. Your system may slow down or crash. Consider closing unused applications.",
                urgency=0.85,
                importance=0.85,
                intrusiveness=0.3,
            ))

        # Disk space low
        disk_free = disk.get("free_bytes")
        if disk_free is not None and disk_free < 5 * 1024 ** 3:  # < 5 GB
            free_gb = disk_free / 1024 ** 3
            candidates.append(self._make(
                title="Low Disk Space",
                message=f"Only {free_gb:.1f} GB of disk space remaining. This may cause failures in builds or file operations.",
                urgency=0.8,
                importance=0.8,
                intrusiveness=0.25,
            ))

        # Coding context
        coding_keywords = {"code", "vscode", "pycharm", "python", "intellij", "vim", "nano"}
        if any(kw in active_app for kw in coding_keywords):
            # Check if there are any useful project-level observations
            for obs in observations:
                if "test" in obs.lower() and "fail" in obs.lower():
                    candidates.append(self._make(
                        title="Test Failures Detected",
                        message=f"I noticed: {obs}. Would you like me to investigate?",
                        urgency=0.7,
                        importance=0.75,
                        intrusiveness=0.2,
                    ))
                    break

        return candidates
