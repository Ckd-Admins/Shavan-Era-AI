"""Autonomous Technology Selector for ERA Autonomous Outcome Engine."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Any


class TechSelector:
    """Inspects workspace and selects optimal technology stacks based on requirements."""

    @classmethod
    def select_stack(cls, goal_prompt: str, workspace_path: str) -> Dict[str, Any]:
        prompt_lower = goal_prompt.lower()
        ws = Path(workspace_path)
        existing_files = []
        if ws.exists():
            existing_files = [f.name.lower() for f in ws.glob("*") if f.is_file()]

        # 1. Existing project detection
        if "package.json" in existing_files:
            return {
                "type": "existing_node",
                "frontend": "React / Node.js",
                "build_tool": "npm / vite",
                "test_tool": "npm test",
                "run_command": "npm start",
            }
        elif any(f in existing_files for f in ["pyproject.toml", "requirements.txt", "main.py", "app.py"]):
            return {
                "type": "existing_python",
                "backend": "Python 3",
                "test_tool": "pytest",
                "run_command": "python main.py",
            }

        # 2. New Project Selection based on goal
        if "react" in prompt_lower or "full-stack" in prompt_lower:
            return {
                "type": "new_react",
                "frontend": "React + TypeScript + Vite",
                "styles": "Tailwind / CSS",
                "run_command": "npx vite",
            }
        elif "python" in prompt_lower or "fastapi" in prompt_lower or "backend" in prompt_lower:
            return {
                "type": "new_python",
                "language": "Python 3",
                "framework": "FastAPI / Standard Library",
                "run_command": "python main.py",
            }
        elif any(kw in prompt_lower for kw in ["website", "chatgpt", "expense", "e-commerce", "html"]):
            return {
                "type": "web_standard",
                "frontend": "HTML5 / CSS3 / ES6 JavaScript",
                "storage": "Local JSON / localStorage",
                "run_command": "python -m http.server 8080",
            }
        else:
            return {
                "type": "general_script",
                "language": "Python / JavaScript",
                "run_command": "python main.py",
            }
