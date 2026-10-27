"""ERA Intelligence Core — Risk-Based Permission Engine.

Implements four autonomy modes:
  OFF        — deny everything except passive reads
  ASSIST     — auto-approve only low-risk actions; confirmation for all else
  SUPERVISED — auto-approve low/medium; confirmation for high/critical
  AUTONOMOUS — auto-approve low/medium/high; confirmation for critical only

Emergency stop is a class-level flag that halts all action immediately.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

VALID_MODES = {"OFF", "ASSIST", "SUPERVISED", "AUTONOMOUS"}

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class PermissionEngine:
    """Risk-based permission gating for all ERA actions."""

    # ── Class-level emergency stop ─────────────────────────────────────
    EMERGENCY_STOP_FLAG: bool = False

    @classmethod
    def emergency_stop(cls) -> None:
        cls.EMERGENCY_STOP_FLAG = True

    @classmethod
    def is_stopped(cls) -> bool:
        return cls.EMERGENCY_STOP_FLAG

    @classmethod
    def clear_stop(cls) -> None:
        cls.EMERGENCY_STOP_FLAG = False

    # ── Instance ───────────────────────────────────────────────────────
    def __init__(self, audit_log: Any, mode: str = "SUPERVISED") -> None:
        self._lock = threading.Lock()
        self._pending: Dict[str, Dict[str, Any]] = {}
        self.audit_log = audit_log
        self.set_mode(mode)

    def set_mode(self, mode: str) -> None:
        mode = mode.upper()
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of: {sorted(VALID_MODES)}")
        self.mode = mode

    # ── Core check ────────────────────────────────────────────────────

    def check_permission(
        self,
        action: str,
        tool: str,
        risk_level: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Returns:
            {allowed: bool, requires_confirmation: bool, request_id: Optional[str], reason: str}
        """
        risk_level = risk_level.lower()
        risk_rank  = RISK_ORDER.get(risk_level, 0)

        # Emergency stop overrides everything
        if self.EMERGENCY_STOP_FLAG:
            self.audit_log.record("permission_denied", "system", {
                "action": action, "tool": tool, "reason": "emergency_stop_active"
            }, risk_level)
            return {"allowed": False, "requires_confirmation": False,
                    "request_id": None, "reason": "ERA emergency stop is active"}

        # Determine decision
        decision = self._decide(risk_rank)

        if decision == "allow":
            self.audit_log.record("permission_granted", "system", {
                "action": action, "tool": tool, "risk": risk_level,
                "mode": self.mode, "reason": reason,
            }, risk_level)
            return {"allowed": True, "requires_confirmation": False,
                    "request_id": None, "reason": "Auto-approved"}

        if decision == "confirm":
            req_id = self._create_pending(action, tool, risk_level, reason)
            self.audit_log.record("permission_pending", "system", {
                "action": action, "tool": tool, "risk": risk_level,
                "mode": self.mode, "request_id": req_id,
            }, risk_level)
            return {"allowed": False, "requires_confirmation": True,
                    "request_id": req_id, "reason": "Requires user confirmation"}

        # deny
        self.audit_log.record("permission_denied", "system", {
            "action": action, "tool": tool, "risk": risk_level,
            "mode": self.mode,
        }, risk_level)
        return {"allowed": False, "requires_confirmation": False,
                "request_id": None, "reason": f"Mode '{self.mode}' does not allow {risk_level}-risk actions"}

    def _decide(self, risk_rank: int) -> str:
        """Returns 'allow', 'confirm', or 'deny'."""
        if self.mode == "OFF":
            # Only passive read (risk_rank 0 treated as allow, rest deny)
            return "allow" if risk_rank == 0 else "deny"

        if self.mode == "ASSIST":
            if risk_rank == 0:
                return "allow"
            return "confirm"   # medium, high, critical all require confirmation

        if self.mode == "SUPERVISED":
            if risk_rank <= 1:   # low + medium
                return "allow"
            return "confirm"    # high + critical require confirmation

        if self.mode == "AUTONOMOUS":
            if risk_rank <= 2:   # low + medium + high
                return "allow"
            return "confirm"    # critical still requires confirmation

        return "deny"

    # ── Pending management ────────────────────────────────────────────

    def _create_pending(self, action: str, tool: str, risk_level: str, reason: str) -> str:
        req_id = uuid.uuid4().hex
        with self._lock:
            self._pending[req_id] = {
                "id": req_id,
                "action": action,
                "tool": tool,
                "risk_level": risk_level,
                "reason": reason,
                "created_at": time.time(),
                "status": "pending",
            }
        return req_id

    def respond(self, request_id: str, approved: bool) -> Dict[str, Any]:
        """User responds to a pending permission request."""
        with self._lock:
            req = self._pending.pop(request_id, None)
        if req is None:
            return {"success": False, "message": f"Request '{request_id}' not found or already resolved"}

        status = "approved" if approved else "denied"
        req["status"] = status
        req["resolved_at"] = time.time()

        self.audit_log.record(f"permission_{status}", "user", {
            "request_id": request_id, "action": req["action"],
            "tool": req["tool"], "risk": req["risk_level"],
        }, req["risk_level"])

        return {"success": True, "status": status, "action": req["action"]}

    def list_pending(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._pending.values())

    def get_pending(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._pending.get(request_id)
