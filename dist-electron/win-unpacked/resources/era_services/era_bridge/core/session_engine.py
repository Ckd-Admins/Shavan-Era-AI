"""Pure conversational state-machine logic for Era Bridge.

Deliberately has zero knowledge of HTTP, sessions storage, or how to
actually reach Era Local Agent -- it just looks at a command catalog
and a session's collected params/confirmation, and decides what
happens next. This separation makes it fully testable without any
mocking of network calls or databases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from core.command_catalog import CommandSpec


@dataclass
class NextStep:
    """Describes what Era Bridge should do next for a given session."""

    kind: str  # "unknown_command" | "not_enabled" | "needs_input" | "needs_confirmation" | "ready"
    message: str = ""
    param: Optional[str] = None


def resolve_next_step(
    catalog: Dict[str, CommandSpec],
    command_name: str,
    params: Dict[str, str],
    confirmed: bool,
) -> NextStep:
    """Given a command name and what's been collected so far, decides the next step."""
    spec = catalog.get(command_name.strip().lower())
    if spec is None:
        return NextStep(kind="unknown_command", message=f"Unknown command: '{command_name}'")

    if not spec.enabled:
        return NextStep(
            kind="not_enabled",
            message=(
                f"'{command_name}' exists on Era Local Agent but isn't enabled through Era Bridge "
                "yet -- it needs an explicitly approved Local Agent update first (Phase 3)."
            ),
        )

    missing = [
        p for p in spec.params
        if p.required and not (params.get(p.name) or "").strip()
    ]
    if missing:
        next_param = missing[0]
        return NextStep(kind="needs_input", message=next_param.prompt, param=next_param.name)

    if spec.requires_confirmation and not confirmed:
        return NextStep(
            kind="needs_confirmation",
            message=f"Are you sure you want to run '{command_name}'? This can't be easily undone.",
        )

    return NextStep(kind="ready")
