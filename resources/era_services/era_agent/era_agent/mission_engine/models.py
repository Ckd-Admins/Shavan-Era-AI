"""ERA Mission Engine Data Models.

Defines Mission, MissionStep, MissionState, StepStatus, RiskLevel, and related types.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MissionState(str, Enum):
    CREATED = "CREATED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"


class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    EXTERNAL_SIDE_EFFECT = "EXTERNAL_SIDE_EFFECT"
    DESTRUCTIVE = "DESTRUCTIVE"


@dataclass
class MissionStep:
    id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    description: str = ""
    action: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    verification: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW_RISK
    confirmation_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "action": self.action,
            "args": self.args,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "verification": self.verification,
            "dependencies": self.dependencies,
            "risk_level": self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level),
            "confirmation_required": self.confirmation_required,
        }


@dataclass
class Mission:
    id: str = field(default_factory=lambda: f"mission_{uuid.uuid4().hex[:8]}")
    goal: str = ""
    state: MissionState = MissionState.CREATED
    steps: List[MissionStep] = field(default_factory=list)
    current_step_index: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    results: List[Any] = field(default_factory=list)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    recovery_attempts: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    final_summary: Optional[Dict[str, Any]] = None

    @property
    def current_step(self) -> Optional[MissionStep]:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "state": self.state.value if hasattr(self.state, "value") else str(self.state),
            "steps": [step.to_dict() for step in self.steps],
            "current_step_index": self.current_step_index,
            "current_step": self.current_step.to_dict() if self.current_step else None,
            "context": self.context,
            "results": self.results,
            "failures": self.failures,
            "recovery_attempts": self.recovery_attempts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "final_summary": self.final_summary,
            "progress_percent": int((sum(1 for s in self.steps if s.status == StepStatus.SUCCESS) / max(1, len(self.steps))) * 100),
        }
