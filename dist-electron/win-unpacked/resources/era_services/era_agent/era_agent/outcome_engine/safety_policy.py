"""Confidence & Risk Policy Engine for ERA Outcome Engine."""

from __future__ import annotations

import re
from typing import Any, Dict
from .models import AgentMode, ConfidenceLevel, RiskLevel, TaskNode


class SafetyPolicy:
    """Enforces execution boundaries, risk classification, credential redaction, and confirmation gates."""

    @classmethod
    def evaluate_risk(cls, action_type: str, params: Dict[str, Any]) -> RiskLevel:
        act = action_type.lower()
        cmd = str(params.get("command", "")).lower()

        # Irreversible or destructive operations
        if any(kw in cmd for kw in ["rmdir /s", "del /f", "rm -rf", "format", "shutdown", "drop database"]):
            return RiskLevel.IRREVERSIBLE

        # High risk operations requiring explicit approval
        if act in ["install_software_updates", "submit_form", "request_approval"] or any(
            kw in cmd for kw in ["delete", "remove", "kill", "uninstall", "git push --force", "winget upgrade"]
        ):
            return RiskLevel.HIGH_RISK

        # Reversible file modifications
        if act in ["write_file", "create_directory", "generate_code_files", "apply_code_repair", "fill_form_fields"]:
            return RiskLevel.REVERSIBLE

        return RiskLevel.SAFE

    @classmethod
    def requires_user_confirmation(cls, node: TaskNode, mode: AgentMode = AgentMode.SUPERVISED) -> bool:
        """Determines whether the task action must pause for explicit user approval."""
        if mode == AgentMode.ASSIST:
            return True  # ASSIST mode requires approval for every action

        if mode == AgentMode.OBSERVE:
            # OBSERVE mode prevents modifications altogether
            return node.risk_level != RiskLevel.SAFE

        # SUPERVISED mode (Default)
        if node.risk_level in [RiskLevel.HIGH_RISK, RiskLevel.IRREVERSIBLE]:
            return True

        if node.action_type in ["request_approval", "install_software_updates", "submit_form"]:
            return True

        if node.confidence == ConfidenceLevel.LOW:
            return True

        return False

    @classmethod
    def sanitize_log_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redacts sensitive credentials, passwords, tokens, API keys, and OTPs from log entries."""
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(sens in k_lower for sens in ["pass", "secret", "token", "key", "otp", "auth", "credential"]):
                sanitized[k] = "[REDACTED_SENSITIVE_DATA]"
            elif isinstance(v, dict):
                sanitized[k] = cls.sanitize_log_data(v)
            else:
                sanitized[k] = v
        return sanitized
