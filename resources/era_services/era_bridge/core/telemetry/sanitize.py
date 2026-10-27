"""Client-side privacy gate: only allow-listed identifiers can ever enter the outbox."""

from __future__ import annotations

import re

from core.command_catalog import CATALOG

_IDENT = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_ERROR_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,63}$")
_SENSITIVE = re.compile(r"@|://|[\\/]|(?i:password|secret|token|api[_-]?key|bearer)|[A-Za-z0-9_\-+=]{40,}")
COMPONENTS = {"bridge", "agent", "memory", "frontend", "voice", "vision", "gmail", "whatsapp", "autonomy"}
SEVERITIES = {"info", "warning", "error", "critical"}
# Feature categories Bridge itself can observe. (Voice/Vision/Gmail/... are reported by those components later.)
FEATURES = {"pc_control", "memory"}
MEMORY_OPS = {"context", "ingest"}


def command_id(name: str | None) -> str | None:
    """Only commands that exist in Bridge's own catalog are reported; anything else becomes 'unknown'."""
    if name is None:
        return None
    return name if name in CATALOG or name in MEMORY_OPS else "unknown"


def feature_id(name: str) -> str:
    return name if name in FEATURES else "unknown"


def error_type_from(exc_or_name) -> str:  # noqa: ANN001
    """Exception CLASS name only -- never str(exc), which can contain paths, text or secrets."""
    name = exc_or_name if isinstance(exc_or_name, str) else type(exc_or_name).__name__
    if _ERROR_TYPE.match(name) and not _SENSITIVE.search(name):
        return name
    return "UnknownError"


def component_id(name: str) -> str:
    return name if name in COMPONENTS else "bridge"


def severity_id(name: str) -> str:
    return name if name in SEVERITIES else "error"
