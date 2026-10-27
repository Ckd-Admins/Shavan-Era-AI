"""Command registry for Era Agent.

This module provides a lightweight, decorator-based registry so that
new commands can be added in the future without touching the main
application loop in main.py.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class CommandResult:
    """Represents the outcome of executing a single command."""

    success: bool
    message: str


CommandFunc = Callable[..., CommandResult]


@dataclass
class CommandParam:
    """Description of a parameter accepted by a command."""

    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None


class CommandRegistry:
    """Holds every available command, keyed by its lowercase name."""

    def __init__(self) -> None:
        self._commands: Dict[str, CommandFunc] = {}
        self._descriptions: Dict[str, str] = {}
        self._params: Dict[str, List[CommandParam]] = {}

    def register(
        self,
        name: str,
        description: str = "",
        params: Optional[List[CommandParam]] = None,
    ) -> Callable[[CommandFunc], CommandFunc]:
        """Decorator used to register a function as a command.

        Example:
            @registry.register("open_app", "Opens any app by name", params=[
                CommandParam("app_name", "str", "Name of the app", required=True)
            ])
            def open_app(app_name: Optional[str] = None) -> CommandResult:
                ...
        """

        def decorator(func: CommandFunc) -> CommandFunc:
            key = name.strip().lower()
            self._commands[key] = func
            self._descriptions[key] = description
            self._params[key] = params or []
            return func

        return decorator

    def get(self, name: str) -> Optional[CommandFunc]:
        return self._commands.get(name.strip().lower())

    def list_commands(self) -> Dict[str, str]:
        """Returns a copy of {command_name: description}."""
        return dict(self._descriptions)

    def get_command_specs(self) -> Dict[str, Any]:
        """Returns full specifications of registered commands including parameters."""
        specs = {}
        for name, desc in self._descriptions.items():
            param_list = self._params.get(name, [])
            specs[name] = {
                "description": desc,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                        "default": p.default,
                    }
                    for p in param_list
                ],
            }
        return specs

    def execute(self, name: str, *args: Any, **kwargs: Any) -> CommandResult:
        """Runs a command by name with given args/kwargs and always returns a CommandResult.

        Any unexpected exception raised by a command is caught here so
        the agent never crashes on a single bad command; it is reported
        back as a clean failure message instead.
        """
        func = self.get(name)
        if func is None:
            return CommandResult(False, f"Unknown command: '{name}'")

        try:
            signature = inspect.signature(func)
            signature.bind_partial(*args, **kwargs)
        except TypeError as exc:
            return CommandResult(False, f"Command '{name}' failed with an error: {exc}")

        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - convert any failure to a clean result
            return CommandResult(False, f"Command '{name}' failed with an error: {exc}")


# A single shared registry instance used across the whole project.
registry = CommandRegistry()

