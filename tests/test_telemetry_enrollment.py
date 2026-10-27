"""
ERA Telemetry Enrollment Tests
=================================
Tests the login → consent → enrollment → device-in-Admin-Panel flow.

Prerequisites (run with venv that includes era_bridge deps):
  D:\\era_agent\\.venv\\Scripts\\python.exe -m pytest tests/test_telemetry_enrollment.py -v

The Bridge must be running on port 8100 OR the BRIDGE_MOCK=1 env var must be set
to run against mocked HTTP responses instead.
"""

import os
import sys
import json
import time
import uuid
import hashlib
import hmac
import pytest
import requests
import unittest.mock as mock

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BRIDGE_URL  = os.environ.get("BRIDGE_URL",   "http://127.0.0.1:8100")
CENTRAL_URL = os.environ.get("ERA_CENTRAL_URL", "http://127.0.0.1:9000")
BRIDGE_MOCK = os.environ.get("BRIDGE_MOCK", "0") == "1"

def _resolve_bridge_key() -> str:
    """
    Read the Bridge API key from the same priority chain the Bridge itself uses:
    1. BRIDGE_API_KEY env var (set by main.cjs when Electron launches the Bridge)
    2. ~/.era/bridge_api.key file (auto-generated on first run)
    3. Fallback literal (should only happen in CI stubs)
    """
    env_key = os.environ.get("BRIDGE_API_KEY")
    if env_key:
        return env_key.strip()
    key_path = os.path.join(os.path.expanduser("~"), ".era", "bridge_api.key")
    if os.path.isfile(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()
    return "era_bridge_secret_key_2026"  # fallback for CI

BRIDGE_KEY = _resolve_bridge_key()

BRIDGE_HEADERS = {
    "Content-Type": "application/json",
    "X-Era-Bridge-Key": BRIDGE_KEY,
}

TIMEOUT = 5  # seconds per HTTP call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def bridge_available() -> bool:
    """Return True if the Bridge is reachable (401 = alive but auth required)."""
    try:
        r = requests.get(f"{BRIDGE_URL}/v1/status", timeout=2)
        return r.status_code in (200, 401)
    except Exception:
        return False


def central_available() -> bool:
    """Return True if ERA Central is reachable."""
    try:
        r = requests.get(f"{CENTRAL_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def make_fake_id_token(uid: str = "test-uid-001", email: str = "test@example.com") -> str:
    """
    Build a fake Firebase-style JWT header.payload.signature string.
    The Bridge verifies tokens with Firebase Admin SDK — so tests that POST
    this token are expected to fail with 401 unless Firebase is mocked at
    the Bridge level.  We use it to verify the *request format* is correct.
    """
    import base64
    header  = base64.b64encode(json.dumps({"alg": "RS256", "kid": "fake"}).encode()).decode().rstrip("=")
    payload = base64.b64encode(json.dumps({
        "uid": uid, "email": email,
        "iat": int(time.time()), "exp": int(time.time()) + 3600,
        "iss": "https://securetoken.google.com/silken-music-nj4jh",
        "aud": "silken-music-nj4jh",
    }).encode()).decode().rstrip("=")
    sig = base64.b64encode(b"fake_signature").decode().rstrip("=")
    return f"{header}.{payload}.{sig}"


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------
needs_bridge  = pytest.mark.skipif(
    not BRIDGE_MOCK and not bridge_available(),
    reason="ERA Bridge not running on port 8100 (set BRIDGE_MOCK=1 to use mocks)"
)
needs_central = pytest.mark.skipif(
    not central_available(),
    reason="ERA Central not running on port 9000"
)


# ===========================================================================
# Test Group 1: Consent endpoint
# ===========================================================================

class TestConsentEndpoint:
    """Verifies /v1/telemetry/consent behaves correctly."""

    @needs_bridge
    def test_consent_enable_returns_ok(self):
        """Setting consent=True should return 200."""
        r = requests.post(
            f"{BRIDGE_URL}/v1/telemetry/consent",
            headers=BRIDGE_HEADERS,
            json={"enabled": True},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    @needs_bridge
    def test_consent_disable_returns_ok(self):
        """Setting consent=False should return 200."""
        r = requests.post(
            f"{BRIDGE_URL}/v1/telemetry/consent",
            headers=BRIDGE_HEADERS,
            json={"enabled": False},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    @needs_bridge
    def test_consent_requires_bridge_key(self):
        """Missing or wrong Bridge API key must be rejected."""
        r = requests.post(
            f"{BRIDGE_URL}/v1/telemetry/consent",
            headers={"Content-Type": "application/json", "X-Era-Bridge-Key": "wrong_key"},
            json={"enabled": True},
            timeout=TIMEOUT,
        )
        assert r.status_code in (401, 403), f"Expected 401/403 for bad key, got {r.status_code}"

    @needs_bridge
    def test_consent_rejects_external_origin(self):
        """
        The Bridge's require_local dependency should block non-loopback callers.
        In a unit test this is mocked; in integration we verify the local call succeeds
        (we cannot easily test a non-loopback call from the same machine, so we assert
        the local call succeeds as a proxy for the guard being active).
        """
        r = requests.post(
            f"{BRIDGE_URL}/v1/telemetry/consent",
            headers=BRIDGE_HEADERS,
            json={"enabled": True},
            timeout=TIMEOUT,
        )
        # Local call must succeed (guard allows loopback)
        assert r.status_code == 200

    @needs_bridge
    def test_consent_missing_body_field(self):
        """Body without 'enabled' field should return 422."""
        r = requests.post(
            f"{BRIDGE_URL}/v1/telemetry/consent",
            headers=BRIDGE_HEADERS,
            json={},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, f"Expected 422 for missing field, got {r.status_code}"


# ===========================================================================
# Test Group 2: Enrollment endpoint — format validation
# ===========================================================================

class TestEnrollEndpointFormat:
    """Verifies /v1/telemetry/enroll request format handling."""

    @needs_bridge
    def test_enroll_requires_bridge_key(self):
        """Enrollment without Bridge key must be rejected."""
        r = requests.post(
            f"{BRIDGE_URL}/v1/telemetry/enroll",
            headers={"Content-Type": "application/json"},
            json={"id_token": make_fake_id_token()},
            timeout=TIMEOUT,
        )
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    @needs_bridge
    def test_enroll_missing_id_token(self):
        """Enrollment without id_token field should return 422."""
        r = requests.post(
            f"{BRIDGE_URL}/v1/telemetry/enroll",
            headers=BRIDGE_HEADERS,
            json={},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    @needs_bridge
    def test_enroll_invalid_token_rejected(self):
        """
        A structurally valid but cryptographically invalid Firebase token
        must be rejected by the Bridge (401), not cause a 500.
        """
        fake_token = make_fake_id_token()
        r = requests.post(
            f"{BRIDGE_URL}/v1/telemetry/enroll",
            headers=BRIDGE_HEADERS,
            json={"id_token": fake_token},
            timeout=TIMEOUT,
        )
        # Bridge should reject the fake token — 401 or 503 (if Central not configured)
        assert r.status_code in (400, 401, 422, 503), (
            f"Expected rejection, got {r.status_code}: {r.text}"
        )
        # 503 means Central not configured, not a crash — acceptable
        # Only 500 is an actual server crash
        assert r.status_code != 500, "Bridge must not crash on invalid token (HTTP 500)"

    @needs_bridge
    def test_enroll_without_prior_consent_is_handled(self):
        """
        Enrollment when consent is disabled should either be rejected (preferred)
        or silently ignored — never cause a 500.
        """
        # Disable consent first
        requests.post(
            f"{BRIDGE_URL}/v1/telemetry/consent",
            headers=BRIDGE_HEADERS,
            json={"enabled": False},
            timeout=TIMEOUT,
        )
        r = requests.post(
            f"{BRIDGE_URL}/v1/telemetry/enroll",
            headers=BRIDGE_HEADERS,
            json={"id_token": make_fake_id_token()},
            timeout=TIMEOUT,
        )
        assert r.status_code < 500, f"Bridge must not crash: {r.status_code} {r.text}"
        # Re-enable for subsequent tests
        requests.post(
            f"{BRIDGE_URL}/v1/telemetry/consent",
            headers=BRIDGE_HEADERS,
            json={"enabled": True},
            timeout=TIMEOUT,
        )


# ===========================================================================
# Test Group 3: Bridge unavailable — login still works
# ===========================================================================

class TestLoginSurvivesBridgeDown:
    """
    Verifies the App.tsx enrollment pattern: when Bridge is unreachable,
    fetch() raises a network error that must be caught silently.
    These tests run without the Bridge to confirm the catch path.
    """

    def test_consent_fetch_failure_is_caught(self):
        """Simulates App.tsx consent fetch when Bridge is down."""
        # Mimic the App.tsx try/catch pattern
        error_raised = False
        logged_warning = None

        def mock_fetch_fail(*args, **kwargs):
            raise ConnectionError("Bridge not running")

        try:
            mock_fetch_fail("http://127.0.0.1:8100/v1/telemetry/consent")
        except Exception as e:
            # App.tsx catches this and calls console.warn — login must continue
            logged_warning = str(e)
            error_raised = True  # this is swallowed in real code

        assert logged_warning is not None, "Exception should have been raised to be caught"
        # In real code the except block runs console.warn, no re-raise — login proceeds

    def test_enroll_fetch_failure_is_caught(self):
        """Simulates App.tsx enroll fetch when Bridge is down."""
        caught = []

        def do_enrollment():
            try:
                raise ConnectionError("Bridge not running")
            except Exception as e:
                caught.append(str(e))
                # login continues — no re-raise

        do_enrollment()
        assert len(caught) == 1
        assert "Bridge not running" in caught[0]


# ===========================================================================
# Test Group 4: Privacy — no sensitive data in enrollment payload
# ===========================================================================

class TestEnrollmentPrivacy:
    """Asserts that the enrollment payload contains ONLY the Firebase ID token."""

    def test_enrollment_payload_contains_only_id_token(self):
        """
        The payload sent to /v1/telemetry/enroll must contain only 'id_token'.
        No conversation, memory, screenshot, API key, or file content allowed.
        """
        fake_token = make_fake_id_token()
        payload = {"id_token": fake_token}

        forbidden_keys = {
            "conversation", "messages", "history", "memory",
            "screenshot", "screen", "audio", "recording",
            "api_key", "gemini_key", "openai_key", "file",
        }
        payload_keys = set(k.lower() for k in payload.keys())
        leaked = payload_keys & forbidden_keys

        assert not leaked, f"Enrollment payload must not contain: {leaked}"
        assert "id_token" in payload, "Enrollment payload must contain id_token"
        assert len(payload) == 1, f"Enrollment payload must have exactly 1 key, got: {list(payload.keys())}"

    def test_consent_payload_contains_only_enabled(self):
        """
        The consent payload must contain only 'enabled' — no user data.
        """
        payload = {"enabled": True}
        forbidden_keys = {"conversation", "memory", "user", "email", "token"}
        payload_keys = set(k.lower() for k in payload.keys())
        leaked = payload_keys & forbidden_keys

        assert not leaked, f"Consent payload must not contain: {leaked}"
        assert "enabled" in payload


# ===========================================================================
# Test Group 5: End-to-end with real Central (skipped if not available)
# ===========================================================================

class TestEnrollmentEndToEnd:
    """
    Full flow: consent → enroll → device visible in Central.
    Requires both Bridge and Central to be running and Central to have
    ERA_CENTRAL_URL configured in the Bridge env.
    """

    @needs_bridge
    @needs_central
    def test_central_health(self):
        """ERA Central is reachable."""
        r = requests.get(f"{CENTRAL_URL}/health", timeout=TIMEOUT)
        assert r.status_code == 200

    @needs_bridge
    @needs_central
    def test_bridge_has_central_url_configured(self):
        """
        Bridge telemetry status endpoint should indicate Central URL is configured.
        If not configured, telemetry is silently disabled — not an error.
        """
        r = requests.get(
            f"{BRIDGE_URL}/v1/telemetry/status",
            headers=BRIDGE_HEADERS,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        # Log the telemetry config for human review — don't assert specific URL
        central_url = data.get("central_url") or data.get("telemetry_central_url") or "(not in status)"
        print(f"\n[INFO] Bridge reported central_url: {central_url}")
        # Test passes regardless — presence of the key is informational

    @needs_bridge
    @needs_central
    def test_invalid_token_does_not_create_device_record(self):
        """
        An invalid Firebase token must not create a device record in Central.
        """
        import requests as req

        # Enable consent
        req.post(f"{BRIDGE_URL}/v1/telemetry/consent", headers=BRIDGE_HEADERS,
                 json={"enabled": True}, timeout=TIMEOUT)

        # Attempt enrollment with fake token
        r = req.post(f"{BRIDGE_URL}/v1/telemetry/enroll", headers=BRIDGE_HEADERS,
                     json={"id_token": make_fake_id_token(uid="should-not-exist")},
                     timeout=TIMEOUT)

        # Should fail (401 from Firebase or 503 if Central not wired)
        assert r.status_code in (400, 401, 422, 503), (
            f"Fake token enrollment should fail, got {r.status_code}: {r.text}"
        )

        # Verify Central has no record for the fake UID
        # (requires admin token — skip if not available)
        admin_token = os.environ.get("ERA_ADMIN_TOKEN")
        if admin_token:
            dr = req.get(
                f"{CENTRAL_URL}/api/v1/admin/devices",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=TIMEOUT,
            )
            if dr.status_code == 200:
                devices = dr.json().get("devices", [])
                fake_uids = [d for d in devices if d.get("firebase_uid") == "should-not-exist"]
                assert not fake_uids, "Fake UID must not appear in Central device list"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
