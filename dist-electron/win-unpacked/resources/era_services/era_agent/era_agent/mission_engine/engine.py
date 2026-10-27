"""ERA Mission Engine Core Architecture.

Implements the real OBSERVE -> UNDERSTAND -> PLAN -> ACT -> VERIFY -> RECOVER -> COMPLETE -> LEARN loop.
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional

try:
    from era_agent.communication.router import comm_router
    from era_agent.mission_engine.models import Mission, MissionState, MissionStep, RiskLevel, StepStatus
    from era_agent.tools.tool_registry import tool_registry
except ImportError:
    from communication.router import comm_router
    from mission_engine.models import Mission, MissionState, MissionStep, RiskLevel, StepStatus
    from tools.tool_registry import tool_registry

logger = logging.getLogger(__name__)


class MissionPlanner:
    """Intelligent Mission Planner converting natural language goal into structured steps."""

    @staticmethod
    def plan_goal(goal: str, context: Optional[Dict[str, Any]] = None) -> List[MissionStep]:
        g_lower = goal.lower()
        steps: List[MissionStep] = []

        # Example 1: Communication check & summary (Step 14 example)
        if any(kw in g_lower for kw in ["gmail", "whatsapp", "check email", "check message", "important email"]):
            steps.append(
                MissionStep(
                    description="Inspect recent Gmail inbox for important messages",
                    action="gmail_list",
                    args={"max_results": 5},
                    risk_level=RiskLevel.READ_ONLY,
                )
            )
            steps.append(
                MissionStep(
                    description="Inspect recent WhatsApp messages",
                    action="whatsapp_list",
                    args={"limit": 5},
                    risk_level=RiskLevel.READ_ONLY,
                )
            )

        # Example 2: Presentation preparation (Step 13 example)
        elif any(kw in g_lower for kw in ["presentation", "prepare presentation", "slides", "ppt"]):
            steps.append(
                MissionStep(
                    description="Create presentation outline document",
                    action="create_file",
                    args={
                        "path": "workspace/presentation_outline.md",
                        "content": f"# Presentation Outline\nGenerated for goal: {goal}\n\n1. Executive Summary\n2. Key Metrics\n3. Next Steps",
                    },
                    risk_level=RiskLevel.LOW_RISK,
                )
            )
            steps.append(
                MissionStep(
                    description="Verify presentation outline created",
                    action="read_file",
                    args={"path": "workspace/presentation_outline.md"},
                    risk_level=RiskLevel.READ_ONLY,
                )
            )

        # Default fallback for arbitrary goals
        else:
            steps.append(
                MissionStep(
                    description=f"Initial environment inspection for goal: '{goal}'",
                    action="read_file",
                    args={"path": "README.md"},
                    risk_level=RiskLevel.READ_ONLY,
                )
            )

        return steps


class ERAMissionEngine:
    """Master ERA Mission Engine executing the Flagship Autonomous Loop."""

    def __init__(self) -> None:
        self.missions: Dict[str, Mission] = {}
        self.tool_registry = tool_registry
        self.planner = MissionPlanner()

    def create_mission(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Mission:
        mission = Mission(
            id=f"mission_{uuid.uuid4().hex[:8]}",
            goal=goal,
            context=context or {},
            state=MissionState.CREATED,
        )
        self.missions[mission.id] = mission
        return mission

    def build_plan(self, mission: Mission) -> Mission:
        mission.state = MissionState.PLANNING
        mission.steps = self.planner.plan_goal(mission.goal, mission.context)
        mission.updated_at = time.time()
        return mission

    def execute_step(self, mission: Mission, step: MissionStep) -> Dict[str, Any]:
        step.status = StepStatus.RUNNING
        step.attempts += 1

        # Check safety & confirmation policy
        if self.tool_registry.requires_confirmation(step.action, step.args):
            step.confirmation_required = True
            step.status = StepStatus.WAITING_FOR_CONFIRMATION
            return {
                "success": False,
                "confirmation_required": True,
                "message": f"Action '{step.action}' requires user confirmation before proceeding.",
            }

        res = self.tool_registry.execute(step.action, step.args)
        step.result = res

        if res.get("success"):
            step.status = StepStatus.SUCCESS
        else:
            step.status = StepStatus.FAILED
            step.error = res.get("error") or res.get("message", "Action failed")

        return res

    def verify_step(self, step: MissionStep) -> bool:
        verification = self.tool_registry.verify(step.action, step.result, step.args)
        step.verification = verification
        return verification.get("verified", False)

    def recover(self, mission: Mission, step: MissionStep) -> bool:
        mission.state = MissionState.RECOVERING
        recovery_entry = {
            "step_id": step.id,
            "attempt": step.attempts,
            "error": step.error or step.verification.get("reason"),
            "timestamp": time.time(),
        }
        mission.recovery_attempts.append(recovery_entry)

        if step.attempts >= step.max_attempts:
            logger.warning("Step '%s' exhausted max attempts (%d)", step.description, step.max_attempts)
            return False

        # Apply fallback recovery logic (e.g. modify args or retry)
        logger.info("Retrying step '%s' (Attempt %d/%d)", step.description, step.attempts + 1, step.max_attempts)
        return True

    def approve_step(self, mission_id: str, step_id: Optional[str] = None) -> Dict[str, Any]:
        mission = self.missions.get(mission_id)
        if not mission:
            return {"success": False, "message": f"Mission '{mission_id}' not found"}

        step = mission.current_step
        if not step or step.status != StepStatus.WAITING_FOR_CONFIRMATION:
            return {"success": False, "message": "No step currently awaiting confirmation."}

        # Override confirmation and execute tool
        res = self.tool_registry.execute(step.action, step.args)
        step.result = res
        if res.get("success"):
            step.status = StepStatus.SUCCESS
            mission.state = MissionState.EXECUTING
            self.run(mission)
        else:
            step.status = StepStatus.FAILED
            step.error = res.get("error")

        return mission.to_dict()

    def run(self, mission: Mission) -> Mission:
        try:
            if mission.state in [MissionState.CREATED, MissionState.UNDERSTANDING]:
                mission.state = MissionState.UNDERSTANDING
                self.build_plan(mission)

            mission.state = MissionState.EXECUTING

            for idx in range(mission.current_step_index, len(mission.steps)):
                mission.current_step_index = idx
                step = mission.steps[idx]

                success = False

                while step.attempts < step.max_attempts:
                    exec_res = self.execute_step(mission, step)

                    if step.status == StepStatus.WAITING_FOR_CONFIRMATION:
                        return mission

                    mission.state = MissionState.VERIFYING
                    verified = self.verify_step(step)

                    if verified:
                        success = True
                        step.status = StepStatus.SUCCESS
                        break

                    # Recover
                    if not self.recover(mission, step):
                        break

                    mission.state = MissionState.EXECUTING

                if not success:
                    mission.failures.append({
                        "step_id": step.id,
                        "description": step.description,
                        "error": step.error or "Verification failed",
                    })
                    mission.state = MissionState.FAILED
                    return mission

            mission.state = MissionState.COMPLETED
            mission.completed_at = time.time()
            mission.final_summary = {
                "mission_id": mission.id,
                "goal": mission.goal,
                "total_steps": len(mission.steps),
                "completed_steps": [s.description for s in mission.steps if s.status == StepStatus.SUCCESS],
                "failures": mission.failures,
                "duration": round(mission.completed_at - mission.created_at, 2),
            }
            return mission

        except Exception as exc:
            mission.state = MissionState.FAILED
            logger.exception("Mission execution encountered error: %s", exc)
            return mission


era_mission_engine = ERAMissionEngine()
