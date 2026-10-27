"""ERA Intelligence Core — Context Engine.

Converts raw hardware telemetry into rich, semantic context.
Pure logic; no LLM dependency. LLM narrative generation is optional.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class ContextEngine:
    """Converts computer state into structured semantic context."""

    def build_context(
        self,
        computer_state: Dict[str, Any],
        recent_history: List[Dict[str, Any]],
        workspace_path: str,
    ) -> Dict[str, Any]:
        """Return a full context dict from raw telemetry."""
        battery    = computer_state.get("battery") or {}
        cpu        = computer_state.get("cpu") or {}
        memory     = computer_state.get("memory") or {}
        disk       = computer_state.get("disk") or {}
        network    = computer_state.get("network") or {}
        os_info    = computer_state.get("os_info") or {}
        active_app = computer_state.get("active_app") or ""
        processes  = computer_state.get("running_processes") or []
        activity   = computer_state.get("user_activity", "unknown")

        now = datetime.datetime.now()

        # ── Observations ──────────────────────────────────────────────
        observations = self._build_observations(battery, cpu, memory, disk, network, active_app, activity)

        # ── Sub-contexts ──────────────────────────────────────────────
        user_context = {
            "activity": activity,
            "estimated_task": self._estimate_task(active_app, processes),
        }

        computer_context = {
            "battery_status":  self._battery_status(battery),
            "cpu_status":      self._cpu_status(cpu),
            "memory_status":   self._memory_status(memory),
            "disk_status":     self._disk_status(disk),
            "network_status":  self._network_status(network),
        }

        # Running tools = processes that match known dev/work tools
        tool_names = {p["name"].lower() for p in processes if isinstance(p, dict) and "name" in p}
        running_tools = [n for n in tool_names if any(kw in n for kw in [
            "code", "python", "node", "java", "git", "docker", "chrome",
            "firefox", "terminal", "cmd", "powershell", "postgres", "mysql",
        ])]

        workspace_files = self._list_workspace_files(workspace_path)

        task_context = {
            "active_app":    active_app,
            "running_tools": sorted(running_tools)[:20],
            "workspace_files": workspace_files[:30],
        }

        project_type, key_files = self._detect_project(workspace_path)
        project_context = {
            "detected_project_type": project_type,
            "key_files": key_files,
            "workspace_path": workspace_path,
        }

        hour = now.hour
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        uptime_hours = round(os_info.get("uptime_seconds", 0) / 3600, 1)

        time_context = {
            "local_time":   now.strftime("%Y-%m-%d %H:%M:%S"),
            "time_of_day":  time_of_day,
            "day_of_week":  now.strftime("%A"),
            "uptime_hours": uptime_hours,
        }

        environmental_context = {
            "os":           os_info.get("system", "Unknown"),
            "os_release":   os_info.get("release", "Unknown"),
            "hostname":     os_info.get("hostname", "Unknown"),
            "architecture": os_info.get("architecture", "Unknown"),
        }

        application_context = {
            "active":        active_app,
            "process_count": len(processes),
        }

        return {
            "user_context":          user_context,
            "computer_context":      computer_context,
            "task_context":          task_context,
            "project_context":       project_context,
            "time_context":          time_context,
            "environmental_context": environmental_context,
            "application_context":   application_context,
            "observations":          observations,
        }

    def generate_narrative(self, context: Dict[str, Any]) -> str:
        """Return a concise 1-3 sentence human-readable context summary."""
        obs = context.get("observations", [])
        user = context.get("user_context", {})
        comp = context.get("computer_context", {})
        tc   = context.get("time_context", {})
        proj = context.get("project_context", {})

        parts: List[str] = []

        # Time & task
        tod  = tc.get("time_of_day", "")
        task = user.get("estimated_task", "")
        if tod and task:
            parts.append(f"It's {tod} and the user appears to be {task}.")
        elif tod:
            parts.append(f"It's {tod}.")

        # Project
        ptype = proj.get("detected_project_type")
        if ptype and ptype != "unknown":
            parts.append(f"Active project type: {ptype}.")

        # Critical observations (battery, cpu, memory)
        critical = [o for o in obs if any(kw in o.lower() for kw in ["critical", "low", "high", "pressure"])]
        if critical:
            parts.append(critical[0])

        return " ".join(parts) if parts else "System is idle with no notable conditions."

    # ──────────────────────────────────────────────────────────────────
    # Observation builders
    # ──────────────────────────────────────────────────────────────────

    def _build_observations(
        self, battery, cpu, memory, disk, network, active_app, activity
    ) -> List[str]:
        obs: List[str] = []

        # Battery
        pct = battery.get("percent")
        charging = battery.get("charging")
        if pct is not None:
            if pct <= 10 and charging is False:
                obs.append(f"Battery critically low at {pct:.0f}% with charger disconnected — immediate action required.")
            elif pct <= 20 and charging is False:
                obs.append(f"Battery low at {pct:.0f}% with charger disconnected.")
            elif pct <= 35 and charging is False:
                obs.append(f"Battery at {pct:.0f}% without charger.")

        # CPU
        cpu_pct = cpu.get("percent")
        if cpu_pct is not None:
            if cpu_pct > 90:
                obs.append(f"CPU under extreme load: {cpu_pct:.0f}%.")
            elif cpu_pct > 75:
                obs.append(f"CPU usage high at {cpu_pct:.0f}%.")

        # Memory
        mem_pct = memory.get("percent")
        if mem_pct is not None:
            if mem_pct > 90:
                obs.append(f"Memory pressure critical at {mem_pct:.0f}% used.")
            elif mem_pct > 80:
                obs.append(f"Memory usage high at {mem_pct:.0f}%.")

        # Disk
        disk_free = disk.get("free_bytes")
        if disk_free is not None:
            free_gb = disk_free / 1024 ** 3
            if free_gb < 2:
                obs.append(f"Disk space critically low: only {free_gb:.1f} GB remaining.")
            elif free_gb < 5:
                obs.append(f"Disk space low: {free_gb:.1f} GB remaining.")

        # Network
        online = network.get("online")
        if online is False:
            obs.append("Network appears offline — cloud features unavailable.")

        # App context
        app_lower = (active_app or "").lower()
        if any(kw in app_lower for kw in ["code", "pycharm", "vim", "sublime", "notepad++"]):
            obs.append(f"User appears to be coding in: {active_app}.")
        elif any(kw in app_lower for kw in ["chrome", "firefox", "edge", "brave"]):
            obs.append(f"User is browsing the web ({active_app}).")

        # Activity
        if activity == "idle":
            obs.append("User appears idle (no input detected for >60 seconds).")

        return obs

    # ──────────────────────────────────────────────────────────────────
    # Status string helpers
    # ──────────────────────────────────────────────────────────────────

    def _battery_status(self, b: Dict) -> str:
        pct = b.get("percent")
        charging = b.get("charging")
        if pct is None:
            return b.get("note", "unavailable")
        status = "charging" if charging else "on battery"
        level = "critical" if pct <= 10 else "low" if pct <= 25 else "normal" if pct <= 80 else "full"
        return f"{pct:.0f}% ({level}, {status})"

    def _cpu_status(self, c: Dict) -> str:
        pct = c.get("percent")
        if pct is None:
            return "unavailable"
        level = "idle" if pct < 20 else "moderate" if pct < 60 else "high" if pct < 85 else "extreme"
        return f"{pct:.0f}% ({level})"

    def _memory_status(self, m: Dict) -> str:
        pct = m.get("percent")
        avail = m.get("available_bytes")
        if pct is None:
            return "unavailable"
        avail_gb = f"{avail / 1024**3:.1f} GB free" if avail else ""
        level = "ok" if pct < 70 else "elevated" if pct < 85 else "critical"
        return f"{pct:.0f}% used ({level}{', ' + avail_gb if avail_gb else ''})"

    def _disk_status(self, d: Dict) -> str:
        free = d.get("free_bytes")
        pct  = d.get("percent")
        if free is None:
            return d.get("note", "unavailable")
        free_gb = free / 1024 ** 3
        if pct is None:
            return f"{free_gb:.1f} GB free (usage % unavailable)"
        level = "ok" if pct < 80 else "elevated" if pct < 90 else "critical"
        return f"{free_gb:.1f} GB free ({pct:.0f}% used, {level})"

    def _network_status(self, n: Dict) -> str:
        online = n.get("online")
        if online is None:
            return "unavailable"
        ifaces = n.get("interfaces_up", [])
        return f"online ({', '.join(ifaces[:3])})" if online else "offline"

    # ──────────────────────────────────────────────────────────────────
    # Workspace helpers
    # ──────────────────────────────────────────────────────────────────

    def _list_workspace_files(self, workspace_path: str) -> List[str]:
        try:
            ws = Path(workspace_path)
            if not ws.exists():
                return []
            files = []
            for p in ws.rglob("*"):
                if p.is_file() and not any(part.startswith(".") for part in p.parts):
                    files.append(str(p.relative_to(ws)).replace("\\", "/"))
                    if len(files) >= 50:
                        break
            return files
        except Exception:
            return []

    def _detect_project(self, workspace_path: str):
        """Returns (project_type, key_files)."""
        ws = Path(workspace_path)
        key_files: List[str] = []
        project_type = "unknown"

        indicators = {
            "python":  ["requirements.txt", "setup.py", "pyproject.toml", "setup.cfg", "Pipfile"],
            "node":    ["package.json", "yarn.lock", "pnpm-lock.yaml"],
            "dotnet":  ["*.csproj", "*.sln", "*.fsproj"],
            "java":    ["pom.xml", "build.gradle", "build.gradle.kts"],
            "rust":    ["Cargo.toml"],
            "go":      ["go.mod"],
            "docker":  ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
        }

        try:
            if ws.exists():
                found_files = [f.name for f in ws.iterdir() if f.is_file()]
                for ptype, marker_files in indicators.items():
                    for marker in marker_files:
                        if "*" in marker:
                            # Glob pattern
                            matches = list(ws.glob(marker))
                            if matches:
                                project_type = ptype
                                key_files.extend([m.name for m in matches[:3]])
                                break
                        elif marker in found_files:
                            if project_type == "unknown":
                                project_type = ptype
                            key_files.append(marker)
                    if project_type != "unknown":
                        break
        except Exception:
            pass

        return project_type, key_files[:5]

    def _estimate_task(self, active_app: str, processes: List[Dict]) -> str:
        app = (active_app or "").lower()
        proc_names = " ".join(p.get("name", "").lower() for p in processes if isinstance(p, dict))

        if any(kw in app for kw in ["code", "pycharm", "vim", "sublime", "notepad++"]):
            return "coding"
        if any(kw in app for kw in ["chrome", "firefox", "edge", "brave"]):
            return "web browsing"
        if any(kw in app for kw in ["terminal", "cmd", "powershell", "bash"]):
            return "using terminal"
        if any(kw in app for kw in ["zoom", "teams", "meet", "slack", "discord"]):
            return "in a meeting or communication"
        if "python" in proc_names or "node" in proc_names:
            return "running code"
        if any(kw in app for kw in ["word", "excel", "powerpoint", "docs", "sheets"]):
            return "working on documents"
        return "general computer use"
