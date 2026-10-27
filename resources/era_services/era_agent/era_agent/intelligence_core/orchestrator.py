"""ERA Intelligence Core — Main Intelligence Orchestrator.

This is the top-level coordinator that implements the full ERA loop:

OBSERVE → UNDERSTAND → CONTEXTUALIZE → REASON → DECIDE →
PLAN → PERMISSION CHECK → ACT → VERIFY → RECOVER → REMEMBER → CONTINUE

It integrates ALL existing ERA systems:
- OutcomeEngineOrchestrator (existing: plan/act/verify/recover/checkpoint)
- MissionEngine (existing: mission execution)
- ToolRegistry (existing: tools)
- CommandRegistry (existing: commands)
- ComputerPerception (new: real hardware telemetry)
- ContextEngine (new: semantic context)
- GoalEngine (new: goal vs command classifier)
- InitiativeEngine (new: proactive suggestions)
- PermissionEngine (new: risk-based permission gates)
- AuditLog (new: full action audit trail)
- ModelRouter (new: multi-tier Gemini routing)
- PersonalVault (new: local-first encrypted sensitive storage)
- EventBus (new: event-driven architecture)
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IntelligenceOrchestrator:
    """Master orchestrator for the ERA Personal Computer Intelligence System."""

    def __init__(self, workspace_path: str, autonomy_mode: str = "SUPERVISED") -> None:
        self.workspace_path = workspace_path
        self._stop_event = threading.Event()
        self._perception_thread: Optional[threading.Thread] = None
        self._last_computer_state: Dict[str, Any] = {}
        self._last_context: Dict[str, Any] = {}
        self._active_goals: Dict[str, Any] = {}

        # ── Lazy-load all subsystems ──────────────────────────────────
        self._load_subsystems(workspace_path, autonomy_mode)

    def _load_subsystems(self, workspace_path: str, mode: str) -> None:
        # Audit log first (used by permission engine)
        vault_dir = Path(workspace_path) / ".era_intelligence"
        vault_dir.mkdir(parents=True, exist_ok=True)

        from era_agent.intelligence_core.audit_log import AuditLog
        self.audit_log = AuditLog(str(vault_dir / "audit.jsonl"))

        from era_agent.intelligence_core.permission_engine import PermissionEngine
        self.permission_engine = PermissionEngine(self.audit_log, mode=mode)

        from era_agent.intelligence_core.computer_perception import ComputerPerception
        self.perception = ComputerPerception()

        from era_agent.intelligence_core.context_engine import ContextEngine
        self.context_engine = ContextEngine()

        from era_agent.intelligence_core.goal_engine import GoalEngine
        self.goal_engine = GoalEngine()

        from era_agent.intelligence_core.initiative_engine import InitiativeEngine
        self.initiative_engine = InitiativeEngine()

        from era_agent.intelligence_core.model_router import model_router
        self.model_router = model_router

        from era_agent.intelligence_core.event_bus import EventBus
        self.event_bus = EventBus()

        from era_agent.intelligence_core.personal_vault import PersonalVault
        self.vault = PersonalVault(str(vault_dir / "vault.jsonl"))

        # Existing ERA subsystems
        from era_agent.outcome_engine.orchestrator import OutcomeEngineOrchestrator
        self.outcome_engine = OutcomeEngineOrchestrator(workspace_path, mode=mode if hasattr(mode, 'value') else _parse_mode(mode))  # type: ignore[arg-type]

        from era_agent.tools.tool_registry import tool_registry
        self.tool_registry = tool_registry

        from era_agent.commands import registry as cmd_registry
        self.command_registry = cmd_registry

        logger.info("ERA Intelligence Core loaded. Mode: %s", mode)

    # ------------------------------------------------------------------
    # Main process() — the single entry point for user input
    # ------------------------------------------------------------------

    def process(self, user_input: str, context_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process any user input — command, goal, or question."""
        from era_agent.intelligence_core.permission_engine import PermissionEngine
        if PermissionEngine.is_stopped():
            return {"success": False, "message": "ERA is stopped. Call /intelligence/resume to resume."}

        self.audit_log.record("user_input", "user", {"input": user_input[:500]})

        # 1. OBSERVE — snapshot current state
        try:
            computer_state = self.perception.capture()
            self._last_computer_state = computer_state
        except Exception as exc:
            logger.warning("Perception failed: %s", exc)
            computer_state = {}

        # 2. CONTEXTUALIZE
        try:
            context = self.context_engine.build_context(computer_state, [], self.workspace_path)
            self._last_context = context
        except Exception as exc:
            logger.warning("Context build failed: %s", exc)
            context = {}

        # 3. CLASSIFY: command vs goal
        intent_type = self.goal_engine.classify(user_input)

        if intent_type == "command":
            return self._handle_command(user_input, context)
        else:
            return self._handle_goal(user_input, context)

    # ------------------------------------------------------------------
    # Command handling — delegate to existing registry
    # ------------------------------------------------------------------

    def _handle_command(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Route a command through existing ERA command/tool registries."""
        cmd = user_input.strip().lower()

        # Check tool registry first
        tool = self.tool_registry.get_tool(cmd)
        if tool:
            perm = self.permission_engine.check_permission(
                action=cmd, tool="tool_registry",
                risk_level=_tool_risk(tool), reason=f"Execute tool: {cmd}"
            )
            if not perm["allowed"] and not perm.get("requires_confirmation"):
                return {"success": False, "message": f"Permission denied for '{cmd}'", "request_id": perm.get("request_id")}
            result = self.tool_registry.execute(cmd, {})
            self.audit_log.record("tool_executed", "era", {"tool": cmd, "result": result})
            return result

        # Fall back to command registry
        cmd_fn = self.command_registry.get(cmd)
        if cmd_fn:
            try:
                result = cmd_fn()
                return {"success": result.success, "message": result.message}
            except Exception as exc:
                return {"success": False, "message": str(exc)}

        return {"success": False, "message": f"Unknown command: '{user_input}'. Try /goal for complex objectives."}

    # ------------------------------------------------------------------
    # Goal handling — delegate to OutcomeEngineOrchestrator
    # ------------------------------------------------------------------

    def _handle_goal(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract goal, permission check, then delegate to OutcomeEngine."""
        goal = self.goal_engine.extract_goal(user_input)

        # Permission check for the overall goal
        risk = goal.risk
        perm = self.permission_engine.check_permission(
            action="execute_goal", tool="outcome_engine",
            risk_level=risk, reason=f"Goal: {goal.objective[:100]}"
        )

        if not perm["allowed"] and not perm.get("requires_confirmation"):
            return {
                "success": False,
                "message": "Permission denied. This goal requires user approval.",
                "request_id": perm.get("request_id"),
                "goal": {"id": goal.id, "objective": goal.objective},
            }

        if perm.get("requires_confirmation"):
            return {
                "success": False,
                "message": "This goal requires your confirmation before proceeding.",
                "requires_confirmation": True,
                "request_id": perm.get("request_id"),
                "goal": {"id": goal.id, "objective": goal.objective, "risk": goal.risk},
            }

        # Store goal
        self._active_goals[goal.id] = {"goal": goal, "status": "running"}
        self.audit_log.record("goal_started", "era", {"goal_id": goal.id, "objective": goal.objective})

        # Delegate to existing OutcomeEngine
        try:
            result = self.outcome_engine.submit_goal(user_input)
            # Link task_id back to goal
            task_id = result.get("task_id", "")
            self._active_goals[goal.id]["task_id"] = task_id
            self._active_goals[goal.id]["status"] = result.get("status", "running")
            self.audit_log.record("goal_submitted", "era", {"goal_id": goal.id, "task_id": task_id})
            return {**result, "goal_id": goal.id}
        except Exception as exc:
            self.audit_log.record("goal_failed", "era", {"goal_id": goal.id, "error": str(exc)})
            return {"success": False, "message": f"Goal execution failed: {exc}", "goal_id": goal.id}

    # ------------------------------------------------------------------
    # Status & introspection
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        from era_agent.intelligence_core.permission_engine import PermissionEngine
        return {
            "era_version": "4.0.0-intelligence-core",
            "stopped": PermissionEngine.is_stopped(),
            "mode": self.permission_engine.mode,
            "active_goals": len(self._active_goals),
            "pending_permissions": len(self.permission_engine.list_pending()),
            "pending_initiatives": len(self.initiative_engine.get_pending()),
            "computer_state_available": bool(self._last_computer_state),
            "cloud_model_available": self.model_router.is_available(),
        }

    def get_computer_state(self) -> Dict[str, Any]:
        try:
            state = self.perception.capture()
            self._last_computer_state = state
            return state
        except Exception as exc:
            return {"error": str(exc), "available": False}

    def get_context(self) -> Dict[str, Any]:
        if not self._last_computer_state:
            self._last_computer_state = self.get_computer_state()
        try:
            ctx = self.context_engine.build_context(self._last_computer_state, [], self.workspace_path)
            self._last_context = ctx
            return ctx
        except Exception as exc:
            return {"error": str(exc)}

    def get_insights(self) -> List[Dict[str, Any]]:
        """Run the initiative engine against current context."""
        try:
            computer_state = self.perception.capture()
            ctx = self.context_engine.build_context(computer_state, [], self.workspace_path)
            combined = {**computer_state, "observations": ctx.get("observations", [])}
            initiatives = self.initiative_engine.evaluate(combined)
            return [i.to_dict() for i in initiatives]
        except Exception as exc:
            return [{"error": str(exc)}]

    def get_active_goals(self) -> List[Dict[str, Any]]:
        result = []
        for goal_id, data in self._active_goals.items():
            goal = data["goal"]
            task_id = data.get("task_id")
            task_status = None
            if task_id:
                try:
                    task_status = self.outcome_engine.get_task_status(task_id)
                except Exception:
                    pass
            result.append({
                "goal_id": goal_id,
                "objective": goal.objective,
                "risk": goal.risk,
                "status": data["status"],
                "task_id": task_id,
                "task_status": task_status,
            })
        return result

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def emergency_stop(self) -> Dict[str, Any]:
        from era_agent.intelligence_core.permission_engine import PermissionEngine
        PermissionEngine.emergency_stop()
        self.audit_log.record("emergency_stop", "user", {"reason": "user-initiated emergency stop"})
        logger.critical("ERA EMERGENCY STOP activated.")
        return {"success": True, "message": "ERA emergency stop activated. All autonomous execution halted."}

    def resume(self) -> Dict[str, Any]:
        from era_agent.intelligence_core.permission_engine import PermissionEngine
        PermissionEngine.clear_stop()
        self.audit_log.record("resume", "user", {})
        return {"success": True, "message": "ERA resumed."}

    def set_mode(self, mode: str) -> Dict[str, Any]:
        try:
            self.permission_engine.set_mode(mode)
            self.audit_log.record("mode_changed", "user", {"mode": mode})
            return {"success": True, "mode": mode}
        except ValueError as exc:
            return {"success": False, "message": str(exc)}


def _tool_risk(tool: Any) -> str:
    """Map ToolSpec permission_level to string risk level."""
    try:
        val = tool.permission_level.value.lower()
        if "read" in val:
            return "low"
        if "destructive" in val or "irreversible" in val:
            return "high"
        if "external" in val:
            return "medium"
        return "low"
    except Exception:
        return "low"


def _parse_mode(mode: str):
    """Convert string mode to AgentMode enum if needed."""
    try:
        from era_agent.outcome_engine.models import AgentMode
        return AgentMode(mode.upper())
    except Exception:
        from era_agent.outcome_engine.models import AgentMode
        return AgentMode.SUPERVISED


# Singleton factory — created once with environment config
_orchestrator_instance: Optional[IntelligenceOrchestrator] = None
_orchestrator_lock = threading.Lock()


def get_orchestrator(workspace_path: Optional[str] = None, mode: str = "SUPERVISED") -> IntelligenceOrchestrator:
    """Return the global IntelligenceOrchestrator singleton."""
    global _orchestrator_instance
    with _orchestrator_lock:
        if _orchestrator_instance is None:
            wp = workspace_path or os.getenv("WORKSPACE_DIR", str(Path(__file__).parent.parent.parent / "workspace"))
            _orchestrator_instance = IntelligenceOrchestrator(wp, autonomy_mode=mode)
    return _orchestrator_instance
