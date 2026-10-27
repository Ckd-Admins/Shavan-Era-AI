"""Task State Checkpoint Manager for ERA Outcome Engine."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from .task_graph import TaskGraph


class CheckpointManager:
    """Saves and restores durable task graph checkpoints for pause/resume and crash recovery."""

    def __init__(self, workspace_path: str):
        self.checkpoint_dir = Path(workspace_path) / ".checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, task_id: str, graph: TaskGraph, status: str, why_trace: List[Any] = None) -> str:
        trace_serialized = []
        if why_trace:
            for entry in why_trace:
                if hasattr(entry, "model_dump"):
                    trace_serialized.append(entry.model_dump())
                elif isinstance(entry, dict):
                    trace_serialized.append(entry)

        data = {
            "task_id": task_id,
            "status": status,
            "timestamp": time.time(),
            "graph": graph.get_summary(),
            "contract": graph.contract.model_dump() if hasattr(graph.contract, "model_dump") else graph.contract,
            "why_trace": trace_serialized,
        }
        file_path = self.checkpoint_dir / f"{task_id}.json"
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return str(file_path)

    def load_checkpoint(self, task_id: str) -> Optional[Dict[str, Any]]:
        file_path = self.checkpoint_dir / f"{task_id}.json"
        if not file_path.exists():
            return None
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        results = []
        for p in self.checkpoint_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                results.append({
                    "task_id": data.get("task_id"),
                    "status": data.get("status"),
                    "timestamp": data.get("timestamp"),
                    "objective": data.get("contract", {}).get("objective"),
                })
            except Exception:
                pass
        return results
