"""Data models for ERA Personal Computer Intelligence Core."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def uid(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex


def json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {k: json_safe(v) for k, v in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def emit_json(value: Any) -> str:
    return json.dumps(json_safe(value), ensure_ascii=False, indent=2, default=str)


@dataclass
class BatteryState:
    percent: Optional[float] = None
    charging: Optional[bool] = None


@dataclass
class ComputerState:
    timestamp: str
    os: str
    hostname: str
    uptime_seconds: Optional[float]
    battery: BatteryState
    cpu_percent: Optional[float]
    memory_percent: Optional[float]
    memory_available_bytes: Optional[int]
    disk_total_bytes: Optional[int]
    disk_free_bytes: Optional[int]
    network_online: Optional[bool]
    active_app: Optional[str] = None
    running_apps: List[str] = field(default_factory=list)
    devices: List[str] = field(default_factory=list)
    notifications: List[Dict[str, Any]] = field(default_factory=list)
    updates: List[Dict[str, Any]] = field(default_factory=list)
    screen_context: Optional[Dict[str, Any]] = None
    user_activity: Optional[str] = None
    security_state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CurrentContext:
    timestamp: str
    user_context: Dict[str, Any]
    computer_context: Dict[str, Any]
    task_context: Dict[str, Any]
    project_context: Dict[str, Any]
    time_context: Dict[str, Any]
    application_context: Dict[str, Any]
    environmental_context: Dict[str, Any]
    observations: List[str] = field(default_factory=list)


@dataclass
class Goal:
    id: str
    objective: str
    constraints: List[str]
    resources: List[str]
    unknowns: List[str]
    risk: str
    completion_criteria: List[str]
    status: str = "created"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    id: str
    goal_id: str
    title: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    priority: int = 50
    status: str = "pending"
    tool_name: Optional[str] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None
    attempts: int = 0
    max_attempts: int = 3
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class Plan:
    id: str
    goal_id: str
    tasks: List[Task]
    created_at: str = field(default_factory=utc_now)
    revision: int = 1


@dataclass
class Tool:
    name: str
    description: str
    capabilities: List[str]
    risk_level: str
    required_permissions: List[str]
    handler: Any  # Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
    verifier: Optional[Any] = None  # Optional[Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]]
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionRequest:
    id: str
    action: str
    tool: str
    risk_level: str
    reason: str
    status: str = "pending"
    created_at: str = field(default_factory=utc_now)
    resolved_at: Optional[str] = None


@dataclass
class VerificationResult:
    status: str  # success, failure, partial_success, unknown
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    success: bool
    status: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Initiative:
    id: str
    title: str
    message: str
    relevance: float
    importance: float
    urgency: float
    confidence: float
    intrusiveness: float
    created_at: str = field(default_factory=utc_now)
    status: str = "suggested"


@dataclass
class AuditEvent:
    id: str
    event_type: str
    timestamp: str
    actor: str
    payload: Dict[str, Any]
