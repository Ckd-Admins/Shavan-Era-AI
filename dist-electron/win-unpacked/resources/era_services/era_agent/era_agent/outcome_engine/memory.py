"""Long-Term & Temporary Working Memory Manager for ERA Outcome Engine."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskMemoryManager:
    """Manages selective long-term workflow memory and temporary working memory."""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)
        self.memory_file = self.workspace_path / "task_memory.json"
        self.working_memory: Dict[str, Any] = {}
        self._ensure_memory_file()

    def _ensure_memory_file(self) -> None:
        if not self.memory_file.exists():
            try:
                self.memory_file.write_text(json.dumps({"workflows": [], "successful_recoveries": {}}), encoding="utf-8")
            except Exception:
                pass

    def record_successful_workflow(self, goal_prompt: str, stack_info: Dict[str, Any], deliverables: List[str]) -> None:
        """Selectively stores useful workflow patterns in long-term memory."""
        try:
            data = json.loads(self.memory_file.read_text(encoding="utf-8"))
            data["workflows"].append({
                "prompt": goal_prompt,
                "stack": stack_info,
                "deliverables": deliverables,
                "timestamp": time.time(),
            })
            self.memory_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def search_similar_workflow(self, goal_prompt: str) -> Optional[Dict[str, Any]]:
        """Retrieves matching workflow pattern from long-term memory if available."""
        try:
            data = json.loads(self.memory_file.read_text(encoding="utf-8"))
            workflows = data.get("workflows", [])
            for wf in reversed(workflows):
                if any(word in goal_prompt.lower() for word in wf.get("prompt", "").lower().split()):
                    return wf
        except Exception:
            pass
        return None

    def set_working_memory(self, key: str, value: Any) -> None:
        self.working_memory[key] = value

    def get_working_memory(self, key: str, default: Any = None) -> Any:
        return self.working_memory.get(key, default)

    def clear_working_memory(self) -> None:
        """Purges short-lived temporary task working memory upon completion."""
        self.working_memory.clear()
