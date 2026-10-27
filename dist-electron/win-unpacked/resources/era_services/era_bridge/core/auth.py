"""API key authentication for Era Bridge.

Every route except GET /v1/health requires the X-Era-Bridge-Key header to
match config.settings.BRIDGE_API_KEY (compared in constant time). This
protects Bridge's own surface; Era Local Agent has its own, separate key.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from config import settings


def keys_match(provided: str | None, expected: str) -> bool:
    if not provided:
        return False
    return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


async def verify_api_key(x_era_bridge_key: str | None = Header(default=None)) -> None:
    if not keys_match(x_era_bridge_key, settings.BRIDGE_API_KEY):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Era-Bridge-Key header.")


def create_command_auth_token(device_id: str, status: str, lease_expires_at: float, ttl_seconds: int = 30) -> str:
    """Creates a short-lived, tamper-proof authorization token for Local Agent command execution.
    
    Signed with settings.AGENT_API_KEY so only an authorized Bridge can generate it.
    """
    import base64
    import hmac
    import hashlib
    import json
    import time
    import secrets

    now = time.time()
    payload = {
        "device_id": device_id,
        "status": status,
        "lease_expires_at": lease_expires_at,
        "issued_at": now,
        "expires_at": now + ttl_seconds,
        "nonce": secrets.token_hex(8),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")
    sig = hmac.new(settings.AGENT_API_KEY.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"
