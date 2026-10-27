"""Unified ERA Tool Registry & Safety Engine.

Manages tool definitions, arguments schema, risk levels, confirmation rules,
execution handlers, and empirical verification handlers.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    from era_agent.mission_engine.models import RiskLevel
except ImportError:
    from mission_engine.models import RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    name: str
    description: str
    arguments_schema: Dict[str, Any]
    permission_level: RiskLevel
    confirmation_required: bool
    execution_handler: Callable[..., Any]
    verification_handler: Optional[Callable[[Any, Dict[str, Any]], Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments_schema": self.arguments_schema,
            "permission_level": self.permission_level.value,
            "confirmation_required": self.confirmation_required,
        }


class ERAToolRegistry:
    """Unified ERA Tool Registry & Safety Policy Engine."""

    def __init__(self) -> None:
        self.tools: Dict[str, ToolSpec] = {}
        self._register_default_tools()

    def register(
        self,
        name: str,
        description: str,
        arguments_schema: Dict[str, Any],
        permission_level: RiskLevel = RiskLevel.LOW_RISK,
        confirmation_required: bool = False,
        verification_handler: Optional[Callable[[Any, Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> Callable:
        """Decorator to register a function as an ERA tool."""

        def decorator(func: Callable) -> Callable:
            self.tools[name.lower()] = ToolSpec(
                name=name.lower(),
                description=description,
                arguments_schema=arguments_schema,
                permission_level=permission_level,
                confirmation_required=confirmation_required,
                execution_handler=func,
                verification_handler=verification_handler,
            )
            return func

        return decorator

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        return self.tools.get(name.lower())

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        return {name: spec.to_dict() for name, spec in self.tools.items()}

    def requires_confirmation(self, name: str, args: Dict[str, Any]) -> bool:
        tool = self.get_tool(name)
        if not tool:
            return False
        if tool.confirmation_required:
            return True
        if tool.permission_level in [RiskLevel.EXTERNAL_SIDE_EFFECT, RiskLevel.DESTRUCTIVE]:
            return True
        return False

    def execute(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{name}' not found in ERA Tool Registry",
            }
        try:
            res = tool.execution_handler(**args)
            if isinstance(res, dict):
                return res
            return {"success": True, "result": res}
        except Exception as exc:
            logger.exception("Tool execution failed: %s", name)
            return {"success": False, "error": str(exc)}

    def verify(self, name: str, result: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if tool and tool.verification_handler:
            try:
                return tool.verification_handler(result, args)
            except Exception as exc:
                return {"verified": False, "reason": f"Verification error: {exc}"}

        # Default verification logic
        if isinstance(result, dict):
            if result.get("success") is True:
                return {"verified": True, "reason": result.get("message", "Tool reported success")}
            return {"verified": False, "reason": result.get("error") or result.get("message", "Tool reported failure")}
        return {"verified": bool(result), "reason": "Execution returned non-empty response"}

    def _register_default_tools(self) -> None:
        """Register built-in ERA capabilities (PC, Files, Browser, Dev)."""

        # PC Tools
        @self.register(
            "open_app",
            "Opens an application by name on the host computer.",
            {"app_name": {"type": "string", "required": True}},
            permission_level=RiskLevel.LOW_RISK,
        )
        def open_app(app_name: str) -> Dict[str, Any]:
            try:
                try:
                    from era_agent.commands.system_commands import open_app as sys_open_app
                except ImportError:
                    from commands.system_commands import open_app as sys_open_app
                res = sys_open_app(app_name=app_name)
                return {"success": res.success, "message": res.message}
            except Exception as e:
                try:
                    import os
                    os.startfile(app_name)
                    return {"success": True, "message": f"Launched application '{app_name}'"}
                except Exception as inner_e:
                    return {"success": False, "error": f"Failed to open '{app_name}': {inner_e}"}

        @self.register(
            "close_app",
            "Closes a running application by process name.",
            {"app_name": {"type": "string", "required": True}},
            permission_level=RiskLevel.LOW_RISK,
        )
        def close_app(app_name: str) -> Dict[str, Any]:
            try:
                subprocess.run(f'taskkill /F /IM "{app_name}.exe"', shell=True, check=False)
                return {"success": True, "message": f"Terminated process '{app_name}'"}
            except Exception as e:
                return {"success": False, "error": f"Failed to close '{app_name}': {e}"}

        @self.register(
            "shutdown",
            "Shuts down or restarts the host PC.",
            {"restart": {"type": "boolean", "default": False}},
            permission_level=RiskLevel.EXTERNAL_SIDE_EFFECT,
            confirmation_required=True,
        )
        def shutdown(restart: bool = False) -> Dict[str, Any]:
            flag = "/r" if restart else "/s"
            subprocess.run(f"shutdown {flag} /t 30", shell=True)
            return {"success": True, "message": f"System scheduled for {'restart' if restart else 'shutdown'}."}

        # File Tools
        @self.register(
            "create_file",
            "Creates a file at the specified path with content.",
            {"path": {"type": "string", "required": True}, "content": {"type": "string", "default": ""}},
            permission_level=RiskLevel.LOW_RISK,
            verification_handler=lambda res, args: {
                "verified": os.path.exists(args.get("path", "")),
                "reason": f"File '{args.get('path')}' verified on disk" if os.path.exists(args.get("path", "")) else "File missing",
            },
        )
        def create_file(path: str, content: str = "") -> Dict[str, Any]:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"success": True, "message": f"Created file '{path}'", "path": path}
            except Exception as e:
                return {"success": False, "error": str(e)}

        @self.register(
            "read_file",
            "Reads and returns text from a file.",
            {"path": {"type": "string", "required": True}},
            permission_level=RiskLevel.READ_ONLY,
        )
        def read_file(path: str) -> Dict[str, Any]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = f.read()
                return {"success": True, "content": data, "path": path}
            except Exception as e:
                return {"success": False, "error": str(e)}

        @self.register(
            "delete_file",
            "Deletes a file permanently.",
            {"path": {"type": "string", "required": True}},
            permission_level=RiskLevel.DESTRUCTIVE,
            confirmation_required=True,
            verification_handler=lambda res, args: {
                "verified": not os.path.exists(args.get("path", "")),
                "reason": "File removal verified" if not os.path.exists(args.get("path", "")) else "File still exists",
            },
        )
        def delete_file(path: str) -> Dict[str, Any]:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    return {"success": True, "message": f"Deleted file '{path}'"}
                return {"success": False, "error": f"File '{path}' does not exist"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # Browser Tools
        @self.register(
            "open_url",
            "Opens a web URL in the default browser.",
            {"url": {"type": "string", "required": True}},
            permission_level=RiskLevel.LOW_RISK,
        )
        def open_url(url: str) -> Dict[str, Any]:
            import webbrowser
            try:
                webbrowser.open(url)
                return {"success": True, "message": f"Opened URL '{url}'"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # Dev Tools
        @self.register(
            "run_command",
            "Runs a shell command.",
            {"command": {"type": "string", "required": True}, "cwd": {"type": "string"}},
            permission_level=RiskLevel.LOW_RISK,
        )
        def run_command(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
            try:
                res = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=cwd, timeout=30)
                return {
                    "success": res.returncode == 0,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                    "returncode": res.returncode,
                }
            except Exception as e:
                return {"success": False, "error": str(e)}


tool_registry = ERAToolRegistry()
