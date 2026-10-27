"""Goal Interpreter Engine for ERA Autonomous Outcome Engine."""

from __future__ import annotations

import re
from typing import Any, Dict, List
from .models import OutcomeContract, RiskLevel


class GoalInterpreter:
    """Interprets natural-language user requests into structured OutcomeContracts."""

    @classmethod
    def interpret(cls, prompt: str, workspace_files: List[str] | None = None) -> OutcomeContract:
        cleaned = prompt.strip()
        lower = cleaned.lower()
        workspace_files = workspace_files or []

        # Default specifications
        objective = cleaned
        workflow_type = "generic"
        functional_requirements: List[str] = []
        non_functional_requirements: List[str] = ["Responsive design", "Clean modular structure", "Error handling"]
        selected_stack: Dict[str, str] = {}
        deliverables: List[str] = []
        acceptance_criteria: List[str] = []
        risk_level = RiskLevel.SAFE
        allowed_actions = ["create_directory", "write_file", "read_file", "run_command", "probe_http", "probe_process", "system_command"]
        stop_conditions = ["destructive_deletion_requested", "max_retries_exceeded", "credential_required"]

        # WORKFLOW 1: Laptop Maintenance
        if any(kw in lower for kw in ["update", "laptop", "maintenance", "system update", "winget"]):
            workflow_type = "laptop_maintenance"
            objective = "Check laptop for available system & software updates and perform authorized installation."
            functional_requirements = [
                "Inspect system and query update status via winget/system tools",
                "Identify available software package updates",
                "Explain updates requiring explicit user approval or restart",
                "Pause for explicit user confirmation before installing updates",
                "Install authorized software updates",
                "Verify actual installation results",
            ]
            selected_stack = {"os": "Windows", "tool": "winget / powershell"}
            deliverables = ["system_update_report.json"]
            acceptance_criteria = [
                "Available system updates inspected cleanly",
                "User approval requested for installation",
                "Permitted updates installed successfully",
                "Final update status verified",
            ]
            risk_level = RiskLevel.HIGH_RISK

        # WORKFLOW 2: Government Form Helper
        elif any(kw in lower for kw in ["government", "form", "fill form", "official website", "passport", "tax"]):
            workflow_type = "government_form"
            objective = "Assist user in navigating official website and filling form fields safely."
            functional_requirements = [
                "Open requested web portal or form page",
                "Observe page fields and identify missing user data",
                "Fill form fields using user-provided information",
                "Verify entered information matches instructions",
                "Stop before final submission for explicit user review & confirmation",
                "Submit form only after user approval",
                "Verify confirmation receipt",
            ]
            selected_stack = {"automation": "Browser automation adapter / System browser"}
            deliverables = ["form_review_summary.json"]
            acceptance_criteria = [
                "Form fields observed and mapped",
                "Fields filled accurately without fabricating credentials",
                "Execution paused before submission for user review",
                "Explicit user approval received prior to submission",
            ]
            risk_level = RiskLevel.HIGH_RISK

        # WORKFLOW 3: Fix Coding Error
        elif any(kw in lower for kw in ["fix", "bug", "error", "diagnose", "repair", "debug"]):
            workflow_type = "fix_coding_error"
            objective = "Find, reproduce, and fix coding errors in existing project."
            functional_requirements = [
                "Inspect existing workspace project structure and source code",
                "Run test suite or diagnostics to reproduce error",
                "Diagnose root cause (syntax, import, or runtime error)",
                "Apply minimal, targeted code patch modifications",
                "Re-run test suite to verify bug resolution",
            ]
            selected_stack = {"existing": "Python / Workspace files"}
            deliverables = ["diagnostics_report.json"]
            acceptance_criteria = [
                "Workspace diagnostics completed",
                "Failing tests identified and resolved",
                "Project passes test suite cleanly without regressions",
            ]

        # WORKFLOW 4: Game Creation (Temple Run, Arcade, 2D/3D Endless Runner, Canvas Games)
        elif any(kw in lower for kw in ["game", "temple run", "runner", "arcade", "play", "gaming", "canvas game", "3d game", "2d game"]):
            workflow_type = "game_creation"
            objective = f"Build and launch a fully playable 3D/2D interactive game: {cleaned}"
            functional_requirements = [
                "Create complete 3D/2D HTML5 Canvas game engine with smooth 60 FPS loop",
                "Implement player character physics, jumping, sliding, and 3-lane controls (Arrow keys / WASD)",
                "Generate dynamic obstacles (fire pits, low arches, logs), gold coins, and speed progression",
                "Add Web Audio API sound effects, real-time score, coin counter, and high-score saving",
                "Launch local game server on port 8080 and open directly in browser for instant gameplay",
                "Verify zero console errors and HTTP 200 OK status",
            ]
            selected_stack = {"frontend": "HTML5 Canvas / Modern JavaScript", "backend": "Python http.server"}
            deliverables = ["index.html", "styles.css", "game.js", "main.py"]
            acceptance_criteria = [
                "Playable game assets generated in workspace",
                "Local game server launched on port 8080",
                "Game successfully opened in browser for immediate play",
                "HTTP endpoint responds with 200 OK",
            ]

        # WORKFLOW 5: Website Creation (Startup / AI Chat / General Web)
        elif any(kw in lower for kw in ["website", "startup", "responsive website", "html", "chatgpt", "app", "ecommerce"]):
            workflow_type = "website_creation"
            objective = "Build a responsive, modern web application for the startup."
            functional_requirements = [
                "Create modern HTML5 structure with responsive hero section, features, and interactive elements",
                "Apply modern dark-theme CSS layout (flexbox/grid)",
                "Implement interactive JavaScript frontend application logic",
                "Launch local development HTTP server",
                "Verify website responsiveness and zero console errors",
            ]
            selected_stack = {"frontend": "HTML5/CSS3/JavaScript", "backend": "Python http.server"}
            deliverables = ["index.html", "styles.css", "app.js", "main.py"]
            acceptance_criteria = [
                "Core web assets created in workspace",
                "Local dev server launches on port 8080",
                "HTTP endpoint responds with 200 OK",
                "HTML structure validated without syntax errors",
            ]


        # Generic Software Goal Fallback
        else:
            workflow_type = "generic"
            objective = f"Autonomous execution for: {cleaned}"
            functional_requirements = [
                f"Implement core logic for: {cleaned}",
                "Create required files and execute step sequence",
                "Verify task completion criteria",
            ]
            selected_stack = {"language": "Python 3.10+"}
            deliverables = ["main.py", "README.md"]
            acceptance_criteria = [
                "Target files generated successfully",
                "Execution completed without unhandled exceptions",
            ]

        # Safety check: destructive keywords flag HIGH_RISK / IRREVERSIBLE
        if any(kw in lower for kw in ["delete", "remove", "drop", "kill", "format", "wipe", "uninstall"]):
            risk_level = RiskLevel.HIGH_RISK

        return OutcomeContract(
            original_prompt=prompt,
            objective=objective,
            workflow_type=workflow_type,
            functional_requirements=functional_requirements,
            non_functional_requirements=non_functional_requirements,
            selected_stack=selected_stack,
            deliverables=deliverables,
            acceptance_criteria=acceptance_criteria,
            risk_level=risk_level,
            allowed_actions=allowed_actions,
            stop_conditions=stop_conditions,
        )
