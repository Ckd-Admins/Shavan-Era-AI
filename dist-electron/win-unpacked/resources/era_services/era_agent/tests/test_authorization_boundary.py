"""Tests for the ERA Local Agent authorization boundary (agent_security.py).

Tests verify:
  - Active device with valid token -> 200 OK
  - Missing auth token -> 403
  - Invalid HMAC signature -> 403
  - Expired token (expires_at in past) -> 403
  - Revoked device (status=REVOKED) -> 403
  - Suspended device (status=SUSPENDED) -> 403
  - Expired lease / offline grace window expired -> 403
  - Unprotected routes accessible without auth token
  - Wrong agent key -> 401
  - Bypass attempt via GET /execute (not a valid route — should 405)

Runs against the full FastAPI app (ASGI TestClient, no network needed).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Test setup
# ---------------------------------------------------------------------------

TEST_AGENT_KEY = "test-agent-key-for-boundary-tests"
os.environ.setdefault("ERA_AGENT_API_KEY", TEST_AGENT_KEY)

# Import the app AFTER setting env so agent_security picks up the key.
# Use try/except so the test file is importable even if era_agent package
# layout changes during refactoring.
try:
    from api_server import app
except ImportError:
    pytest.skip("api_server not importable in this environment", allow_module_level=True)


client = TestClient(app, raise_server_exceptions=False)

AGENT_KEY_HEADER = {"X-Era-Agent-Key": TEST_AGENT_KEY}


# ---------------------------------------------------------------------------
# Token factory helpers
# ---------------------------------------------------------------------------

def _make_token(
    *,
    status: str = "ACTIVE",
    lease_expires_at: float = 0.0,  # 0.0 = never initialized (local mode, always allowed)
    token_ttl: int = 30,
    time_shift: float = 0.0,        # positive = token issued in the past (ages it)
    tamper_sig: bool = False,
    agent_key: str = TEST_AGENT_KEY,
) -> str:
    """Builds a signed auth token with controllable parameters."""
    now = time.time() - time_shift
    payload = {
        "device_id": "test-device",
        "status": status,
        "lease_expires_at": lease_expires_at,
        "issued_at": now,
        "expires_at": now + token_ttl,
        "nonce": "deadbeef",
    }
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    sig = hmac.new(
        agent_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if tamper_sig:
        sig = sig[:-4] + "0000"  # corrupt last 4 hex chars
    return f"{payload_b64}.{sig}"


def _auth_headers(token: Optional[str] = None, agent_key: str = TEST_AGENT_KEY) -> dict:
    headers = {"X-Era-Agent-Key": agent_key}
    if token is not None:
        headers["X-Era-Auth-Token"] = token
    return headers


def _good_token(**kwargs) -> str:
    return _make_token(**kwargs)


# ---------------------------------------------------------------------------
# Unprotected routes — no auth required
# ---------------------------------------------------------------------------

class TestUnprotectedRoutes:
    """Unprotected routes must respond 200 even with no auth headers."""

    def test_root_no_auth(self):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_status_no_auth(self):
        resp = client.get("/status")
        assert resp.status_code == 200

    def test_commands_no_auth(self):
        resp = client.get("/commands")
        assert resp.status_code == 200

    def test_tools_no_auth(self):
        resp = client.get("/tools")
        assert resp.status_code == 200

    def test_status_with_wrong_key_still_200(self):
        """GET /status is diagnostic — must not require auth."""
        resp = client.get("/status", headers={"X-Era-Agent-Key": "wrong-key"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /execute — authorization gate
# ---------------------------------------------------------------------------

EXECUTE_PAYLOAD = {"command": "lock_computer"}


class TestExecuteAuthorization:
    """POST /execute requires both agent key AND a valid auth token."""

    def test_missing_agent_key_returns_401(self):
        token = _good_token()
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers={"X-Era-Auth-Token": token},  # no X-Era-Agent-Key
        )
        assert resp.status_code == 401

    def test_wrong_agent_key_returns_401(self):
        token = _good_token()
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=_auth_headers(token, agent_key="wrong-key"),
        )
        assert resp.status_code == 401

    def test_missing_auth_token_returns_403(self):
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=AGENT_KEY_HEADER,  # no X-Era-Auth-Token
        )
        assert resp.status_code == 403, resp.text

    def test_invalid_signature_returns_403(self):
        token = _make_token(tamper_sig=True)
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=_auth_headers(token),
        )
        assert resp.status_code == 403, resp.text
        assert "invalid" in resp.json().get("detail", "").lower()

    def test_expired_token_returns_403(self):
        # Issue a token that expired 60 seconds ago.
        token = _make_token(token_ttl=-60, time_shift=0)
        # Rebuild manually: expires_at = now - 60
        now = time.time()
        payload = {
            "device_id": "test-device",
            "status": "ACTIVE",
            "lease_expires_at": 0.0,
            "issued_at": now - 90,
            "expires_at": now - 60,   # expired
            "nonce": "deadbeef",
        }
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        sig = hmac.new(
            TEST_AGENT_KEY.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
        ).hexdigest()
        expired_token = f"{payload_b64}.{sig}"

        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=_auth_headers(expired_token),
        )
        assert resp.status_code == 403, resp.text
        assert "expired" in resp.json().get("detail", "").lower()

    def test_revoked_device_returns_403(self):
        token = _make_token(status="REVOKED")
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=_auth_headers(token),
        )
        assert resp.status_code == 403, resp.text
        assert "revoked" in resp.json().get("detail", "").lower()

    def test_suspended_device_returns_403(self):
        token = _make_token(status="SUSPENDED")
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=_auth_headers(token),
        )
        assert resp.status_code == 403, resp.text
        assert "suspended" in resp.json().get("detail", "").lower()

    def test_offline_grace_expired_returns_403(self):
        # lease_expires_at is 1 hour in the past
        token = _make_token(lease_expires_at=time.time() - 3600, status="ACTIVE")
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=_auth_headers(token),
        )
        assert resp.status_code == 403, resp.text
        assert "offline" in resp.json().get("detail", "").lower() or \
               "grace" in resp.json().get("detail", "").lower()

    def test_malformed_token_returns_403(self):
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=_auth_headers("not-a-valid-token"),
        )
        assert resp.status_code == 403, resp.text

    def test_active_device_local_mode_passes_auth_gate(self):
        """Status=ACTIVE, lease_expires_at=0 (local/unenrolled mode) -> auth gate passes.

        The command itself may fail (no real agent running in tests) but the
        HTTP response must NOT be 401 or 403 -- the auth gate has let it through.
        The command 'lock_computer' may return 200 with success=False or 500 in
        test environment; that is acceptable here.
        """
        token = _good_token(status="ACTIVE", lease_expires_at=0.0)
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=_auth_headers(token),
        )
        # Auth gate passed: response is 200 (command ran/failed) or 500 (internal error)
        # It must NOT be 401 or 403.
        assert resp.status_code not in (401, 403), (
            f"Expected auth gate to pass for active device in local mode, "
            f"got {resp.status_code}: {resp.text}"
        )

    def test_active_device_with_valid_lease_passes_auth_gate(self):
        """Status=ACTIVE, lease_expires_at in the future -> auth gate passes."""
        token = _good_token(
            status="ACTIVE",
            lease_expires_at=time.time() + 900,  # 15 minutes remaining
        )
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=_auth_headers(token),
        )
        assert resp.status_code not in (401, 403), (
            f"Expected auth gate to pass for active device with valid lease, "
            f"got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# POST /api/missions — authorization gate
# ---------------------------------------------------------------------------

MISSION_PAYLOAD = {"goal": "test goal", "context": {}}


class TestMissionsAuthorization:
    def test_missing_token_returns_403(self):
        resp = client.post("/api/missions", json=MISSION_PAYLOAD, headers=AGENT_KEY_HEADER)
        assert resp.status_code == 403

    def test_revoked_returns_403(self):
        token = _make_token(status="REVOKED")
        resp = client.post("/api/missions", json=MISSION_PAYLOAD, headers=_auth_headers(token))
        assert resp.status_code == 403

    def test_valid_token_passes_gate(self):
        token = _good_token()
        resp = client.post("/api/missions", json=MISSION_PAYLOAD, headers=_auth_headers(token))
        assert resp.status_code not in (401, 403)


class TestMissionsApproveAuthorization:
    def test_missing_token_returns_403(self):
        resp = client.post(
            "/api/missions/fake-mission-id/approve",
            headers=AGENT_KEY_HEADER,
        )
        assert resp.status_code == 403

    def test_revoked_returns_403(self):
        token = _make_token(status="REVOKED")
        resp = client.post(
            "/api/missions/fake-mission-id/approve",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 403

    def test_valid_token_passes_gate(self):
        token = _good_token()
        resp = client.post(
            "/api/missions/fake-mission-id/approve",
            headers=_auth_headers(token),
        )
        # Auth gate passes; mission may 404 (doesn't exist) but not 401/403
        assert resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# POST /v1/outcome/submit — authorization gate
# ---------------------------------------------------------------------------

OUTCOME_PAYLOAD = {"prompt": "test outcome goal"}


class TestOutcomeSubmitAuthorization:
    def test_missing_token_returns_403(self):
        resp = client.post("/v1/outcome/submit", json=OUTCOME_PAYLOAD, headers=AGENT_KEY_HEADER)
        assert resp.status_code == 403

    def test_revoked_returns_403(self):
        token = _make_token(status="REVOKED")
        resp = client.post(
            "/v1/outcome/submit", json=OUTCOME_PAYLOAD, headers=_auth_headers(token)
        )
        assert resp.status_code == 403

    def test_valid_token_passes_gate(self):
        token = _good_token()
        resp = client.post(
            "/v1/outcome/submit", json=OUTCOME_PAYLOAD, headers=_auth_headers(token)
        )
        assert resp.status_code not in (401, 403)


class TestOutcomeApproveAuthorization:
    def test_missing_token_returns_403(self):
        resp = client.post("/v1/outcome/approve/fake-task-id", headers=AGENT_KEY_HEADER)
        assert resp.status_code == 403

    def test_revoked_returns_403(self):
        token = _make_token(status="REVOKED")
        resp = client.post(
            "/v1/outcome/approve/fake-task-id", headers=_auth_headers(token)
        )
        assert resp.status_code == 403

    def test_valid_token_passes_gate(self):
        token = _good_token()
        resp = client.post(
            "/v1/outcome/approve/fake-task-id", headers=_auth_headers(token)
        )
        # Auth gate passes; task may 404 (doesn't exist) but not 401/403
        assert resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# Bypass attempt tests
# ---------------------------------------------------------------------------

class TestBypassAttempts:
    """Verify that routes cannot be bypassed through alternate methods or paths."""

    def test_get_execute_returns_405(self):
        """GET /execute is not a valid route — must not succeed."""
        resp = client.get("/execute")
        assert resp.status_code == 405

    def test_execute_without_any_headers_returns_401_or_403(self):
        """No headers at all: must not execute a command."""
        resp = client.post("/execute", json=EXECUTE_PAYLOAD)
        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403 with no auth headers, got {resp.status_code}"
        )

    def test_missions_without_any_headers_returns_401_or_403(self):
        resp = client.post("/api/missions", json=MISSION_PAYLOAD)
        assert resp.status_code in (401, 403)

    def test_outcome_without_any_headers_returns_401_or_403(self):
        resp = client.post("/v1/outcome/submit", json=OUTCOME_PAYLOAD)
        assert resp.status_code in (401, 403)

    def test_key_only_no_token_returns_403(self):
        """Agent key alone is not enough for protected routes."""
        resp = client.post(
            "/execute",
            json=EXECUTE_PAYLOAD,
            headers=AGENT_KEY_HEADER,
        )
        assert resp.status_code == 403
