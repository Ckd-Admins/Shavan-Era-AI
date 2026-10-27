"""ERA Autonomous Outcome Engine Data Models."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    OBSERVING = "OBSERVING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    REVERSIBLE = "REVERSIBLE"
    HIGH_RISK = "HIGH_RISK"
    IRREVERSIBLE = "IRREVERSIBLE"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AgentMode(str, Enum):
    ASSIST = "ASSIST"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"
    OBSERVE = "OBSERVE"


class VerificationEvidence(BaseModel):
    """Empirical proof attached to a verified task step."""

    timestamp: float = Field(default_factory=time.time)
    strategy: str
    passed: bool
    expected: str
    observed: str
    details: Dict[str, Any] = Field(default_factory=dict)


class OutcomeContract(BaseModel):
    """Structured contract defining the user's intended goal and success criteria."""

    goal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_prompt: str
    objective: str
    workflow_type: str = "generic"
    functional_requirements: List[str] = Field(default_factory=list)
    non_functional_requirements: List[str] = Field(default_factory=list)
    selected_stack: Dict[str, str] = Field(default_factory=dict)
    deliverables: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.SAFE
    allowed_actions: List[str] = Field(default_factory=list)
    stop_conditions: List[str] = Field(default_factory=list)
    verification_method: str = "multi_factor"
    created_at: float = Field(default_factory=time.time)


class TaskNode(BaseModel):
    """Single unit of work inside the dynamic task graph."""

    id: str
    title: str
    description: str
    dependencies: List[str] = Field(default_factory=list)
    priority: int = 1
    action_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PLANNING
    risk_level: RiskLevel = RiskLevel.SAFE
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    verification_strategy: str = "exit_code"
    verification_params: Dict[str, Any] = Field(default_factory=dict)
    max_retries: int = 3
    retry_count: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    evidence: Optional[VerificationEvidence] = None
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None


class WhyTraceEntry(BaseModel):
    """Transparent execution summary log entry for user visibility."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    stage: str
    goal: str
    task_id: Optional[str] = None
    action: str
    observed: str
    decision: str
    status: str
    details: Optional[Dict[str, Any]] = None


class ComputerState(BaseModel):
    """Structured snapshot of local computer environment state."""

    timestamp: float = Field(default_factory=time.time)
    workspace_path: str
    active_window: Optional[str] = None
    running_processes: List[str] = Field(default_factory=list)
    open_ports: List[int] = Field(default_factory=list)
    existing_files: List[str] = Field(default_factory=list)
    available_tools: List[str] = Field(default_factory=list)
    services_status: Dict[str, bool] = Field(default_factory=dict)
    update_status: Dict[str, Any] = Field(default_factory=dict)

