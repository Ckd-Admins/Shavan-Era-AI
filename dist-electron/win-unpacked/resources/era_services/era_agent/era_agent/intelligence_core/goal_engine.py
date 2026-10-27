"""ERA Intelligence Core — Goal Engine.

Distinguishes commands (open VS Code) from goals (build me an app).
Extracts structured Goal objects using heuristics + optional LLM.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from typing import Any, Dict, List

from .models import Goal, utc_now


# Goal keywords that indicate a higher-order objective
_GOAL_PATTERNS = [
    r"\bbuild\b", r"\bcreate\b", r"\bdevelop\b", r"\bdesign\b",
    r"\bimplement\b", r"\bwrite.*app\b", r"\bwrite.*project\b",
    r"\bset up\b", r"\bdeploy\b", r"\blaunch\b", r"\brefactor\b",
    r"\bfix all\b", r"\btest\b.*\band\b.*\bfix\b", r"\boptimize\b",
    r"\bautomate\b", r"\bschedule\b.*\btask\b", r"\bmonitor\b",
    r"\binvestigate\b", r"\banalyze\b", r"\bhelp me.*build\b",
    r"\bhelp me.*create\b", r"\bmake.*work\b",
]

_COMMAND_PATTERNS = [
    r"^open\b", r"^close\b", r"^start\b", r"^stop\b", r"^run\b",
    r"^show\b", r"^display\b", r"^turn (on|off)\b",
    r"^send\b.*\bto\b", r"^read\b", r"^check\b",
]


class GoalEngine:
    """Classifies user input and extracts structured goals."""

    def classify(self, prompt: str) -> str:
        """Returns 'command' or 'goal'."""
        lower = prompt.strip().lower()

        # First check command patterns (usually short, imperative)
        for pat in _COMMAND_PATTERNS:
            if re.search(pat, lower):
                return "command"

        # Then check goal patterns
        for pat in _GOAL_PATTERNS:
            if re.search(pat, lower):
                return "goal"

        # Heuristic: if prompt is long and complex, treat as goal
        word_count = len(lower.split())
        if word_count > 10:
            return "goal"

        return "command"

    def extract_goal(self, prompt: str, llm_result: Dict[str, Any] | None = None) -> Goal:
        """Extract a structured Goal from prompt.

        If llm_result is provided (from ModelRouter), use its parsed structure.
        Otherwise use heuristics.
        """
        if llm_result and llm_result.get("success"):
            return self._parse_llm_goal(prompt, llm_result["text"])

        return self._heuristic_goal(prompt)

    # ------------------------------------------------------------------

    def _heuristic_goal(self, prompt: str) -> Goal:
        lower = prompt.lower()

        constraints: List[str] = []
        resources: List[str] = []
        unknowns: List[str] = []
        criteria: List[str] = []
        risk = "low"

        # Detect constraints
        if "no external" in lower or "no cloud" in lower:
            constraints.append("Local/offline only")
        if "fast" in lower or "quickly" in lower:
            constraints.append("Time-sensitive")
        if "secure" in lower or "security" in lower:
            constraints.append("Security-critical")
            risk = "medium"
        if "production" in lower or "live" in lower:
            risk = "high"
            constraints.append("Production environment")

        # Detect resources from keywords
        if "python" in lower:
            resources.append("Python runtime")
        if "javascript" in lower or "node" in lower or "react" in lower:
            resources.append("Node.js runtime")
        if "database" in lower or "sql" in lower:
            resources.append("Database access")
        if "browser" in lower or "web" in lower or "url" in lower:
            resources.append("Browser")

        # Detect unknowns
        if "?" in prompt:
            unknowns.append("Clarification needed on specific requirements")
        if not resources:
            unknowns.append("Technology stack not specified")

        # Derive completion criteria
        if "test" in lower:
            criteria.append("All tests pass")
        if "run" in lower or "start" in lower:
            criteria.append("Application runs without errors")
        if "deploy" in lower:
            criteria.append("Deployment verified and accessible")
        criteria.append("User confirms satisfactory completion")

        # Extract objective: take the full prompt as objective, cleaned
        objective = prompt.strip().rstrip(".")
        if len(objective) > 200:
            objective = objective[:197] + "..."

        return Goal(
            id=uuid.uuid4().hex,
            objective=objective,
            constraints=constraints,
            resources=resources,
            unknowns=unknowns,
            risk=risk,
            completion_criteria=criteria,
            status="created",
            created_at=utc_now(),
            updated_at=utc_now(),
        )

    def _parse_llm_goal(self, prompt: str, llm_text: str) -> Goal:
        """Attempt to parse structured JSON from LLM response; fall back to heuristic."""
        import json
        try:
            # Try to extract JSON block
            match = re.search(r"\{.*\}", llm_text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return Goal(
                    id=uuid.uuid4().hex,
                    objective=data.get("objective", prompt),
                    constraints=data.get("constraints", []),
                    resources=data.get("resources", []),
                    unknowns=data.get("unknowns", []),
                    risk=data.get("risk", "low"),
                    completion_criteria=data.get("completion_criteria", []),
                    status="created",
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
        except Exception:
            pass
        return self._heuristic_goal(prompt)

    def goal_to_llm_prompt(self, goal: Goal) -> str:
        """Convert a Goal to a planning prompt for the ModelRouter."""
        return f"""You are ERA, a proactive computer intelligence system.
The user wants to achieve this goal:

OBJECTIVE: {goal.objective}
CONSTRAINTS: {', '.join(goal.constraints) or 'none'}
RESOURCES: {', '.join(goal.resources) or 'unknown'}
RISK LEVEL: {goal.risk}
COMPLETION CRITERIA: {', '.join(goal.completion_criteria) or 'user confirmation'}

Create a detailed JSON execution plan with this structure:
{{
  "steps": [
    {{"id": "step_1", "title": "...", "description": "...", "action_type": "...", "dependencies": [], "risk": "low|medium|high", "params": {{}}}}
  ]
}}

Supported action_types: inspect_workspace, generate_code_files, write_file, run_command, run_diagnostics, browser_open_form, apply_code_repair, install_packages

Be specific and concrete. Return only valid JSON."""
