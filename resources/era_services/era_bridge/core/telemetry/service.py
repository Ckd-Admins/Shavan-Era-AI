"""Opt-in, metadata-only telemetry to ERA Central.

Privacy model
    * OFF by default. Nothing is queued or sent until the user enables consent AND enrolls.
    * Only allow-listed identifiers, booleans, durations and timestamps ever enter the outbox
      (see ``sanitize.py``). Command text, params, prompts, messages, files, screen/audio/video,
      memory content, API keys and exception messages are never read, stored or sent.
    * Disabling consent purges the outbox and asks the server to erase this installation.
Security model
    * No shared secret: the device signs each request with its own Ed25519 key (identity.py).
    * Central URL must be https (plain http only for loopback development).
    * Telemetry can never break a command: every public ``record_*`` swallows errors.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from core.telemetry import hardware, sanitize
from core.telemetry.identity import DeviceIdentity
from core.telemetry.store import TelemetryStore

logger = logging.getLogger(__name__)
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class TelemetryError(Exception):
    """User-facing problem (bad config, rejected enrollment...). Never contains secrets."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def validate_central_url(url: str) -> str:
    parsed = urlparse(url)
    if not url or parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise TelemetryError("ERA_CENTRAL_URL is not configured.", 503)
    if parsed.scheme == "http" and parsed.hostname not in _LOOPBACK:
        raise TelemetryError("ERA_CENTRAL_URL must use https.", 503)
    if parsed.path not in ("", "/") or parsed.query or parsed.username or parsed.password:
        raise TelemetryError("ERA_CENTRAL_URL must be a bare origin (no path, query or credentials).", 503)
    return f"{parsed.scheme}://{parsed.netloc}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TelemetryService:
    def __init__(
        self,
        directory,  # noqa: ANN001  (Path)
        central_url: str,
        era_version: str,
        heartbeat_seconds: int = 300,
        flush_seconds: int = 60,
        batch_size: int = 100,
        outbox_max: int = 5000,
        reachability: Optional[Callable[[], Awaitable[bool]]] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.store = TelemetryStore(directory, outbox_max)
        self.identity = DeviceIdentity.load_or_create(directory)
        self.central_url_raw = central_url
        self.era_version = era_version
        self.heartbeat_seconds, self.flush_seconds, self.batch_size = heartbeat_seconds, flush_seconds, batch_size
        self._reachability = reachability
        self._transport = transport
        self._http: Optional[httpx.AsyncClient] = None
        self._tasks: List[asyncio.Task] = []
        self._fail_count = 0
        self._next_probe = 0.0  # while the server rejects this device (401), only probe occasionally
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------ state --
    @property
    def consent(self) -> bool:
        return self.store.flag("consent")

    @property
    def enrolled(self) -> bool:
        return self.store.flag("enrolled")

    @property
    def active(self) -> bool:
        return self.consent and self.enrolled

    def status(self) -> Dict[str, Any]:
        try:
            validate_central_url(self.central_url_raw)
            configured = True
        except TelemetryError:
            configured = False
        return {
            "consent": self.consent, "enrolled": self.enrolled, "central_configured": configured,
            "installation_id": self.identity.installation_id, "queued": self.store.size(),
            "needs_reenroll": self.store.flag("needs_reenroll"), "last_error": self.last_error,
        }

    def preview(self, limit: int = 50) -> Dict[str, Any]:
        """Exactly what is waiting to be sent -- shown to the user for transparency."""
        return {"events": [p for _, p in self.store.peek("event", limit)],
                "errors": [p for _, p in self.store.peek("error", limit)]}

    # ----------------------------------------------------------------- transport --
    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            origin = validate_central_url(self.central_url_raw)
            self._http = httpx.AsyncClient(base_url=origin, timeout=10.0, transport=self._transport, follow_redirects=False)
        return self._http

    async def close(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._tasks.clear()
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _signed_post(self, path: str, obj: Dict[str, Any]) -> httpx.Response:
        body = json.dumps(obj, separators=(",", ":")).encode()
        ts, nonce = str(int(time.time())), secrets.token_urlsafe(18)
        sig = self.identity.sign(self.identity.request_message("POST", path, ts, nonce, body))
        headers = {"Content-Type": "application/json", "X-Era-Device": self.identity.installation_id,
                   "X-Era-Timestamp": ts, "X-Era-Nonce": nonce, "X-Era-Signature": sig}
        return await self._client().post(path, content=body, headers=headers)

    # -------------------------------------------------------- consent / enrollment --
    async def set_consent(self, enabled: bool) -> None:
        self.store.set_flag("consent", enabled)
        if enabled:
            return
        self.store.purge_outbox()  # nothing collected before opt-out is ever sent afterwards
        if self.enrolled:
            self.store.set_flag("pending_unenroll", True)
            await self._try_unenroll()

    async def _try_unenroll(self) -> bool:
        try:
            r = await self._signed_post("/api/device/unenroll", {})
        except (httpx.HTTPError, TelemetryError):
            return False  # retried by the flush loop
        if r.status_code in (200, 401):  # 401: server no longer knows us -> nothing left to erase
            self.store.set_flag("pending_unenroll", False)
            self.store.set_flag("enrolled", False)
            return True
        return False

    async def enroll(self, id_token: str) -> Dict[str, Any]:
        """Binds this installation to the signed-in Firebase user. ``id_token`` is used once and not stored."""
        if not self.consent:
            raise TelemetryError("Telemetry is off. Enable it first.", 409)
        validate_central_url(self.central_url_raw)
        ts, nonce = str(int(time.time())), secrets.token_urlsafe(18)
        body = {"id_token": id_token, "installation_id": self.identity.installation_id,
                "public_key": self.identity.public_key_b64, "timestamp": int(ts), "nonce": nonce,
                "signature": self.identity.sign(self.identity.enroll_message(ts, nonce, id_token)),
                "device": hardware.collect(self.era_version)}
        try:
            r = await self._client().post("/api/device/enroll", json=body)
        except httpx.HTTPError as exc:
            raise TelemetryError(f"Could not reach ERA Central ({type(exc).__name__}).", 502) from None
        if r.status_code != 200:
            detail = ""
            try:
                detail = str(r.json().get("detail", ""))[:60]
            except ValueError:
                pass
            raise TelemetryError(f"Enrollment rejected ({r.status_code} {detail}).".strip(), 502 if r.status_code >= 500 else 400)
        self.store.set_flag("enrolled", True)
        self.store.set_flag("needs_reenroll", False)
        self.store.set_flag("pending_unenroll", False)
        self.last_error = None
        return {"installation_id": self.identity.installation_id}

    # ------------------------------------------------------------------ recording --
    def record_usage(self, feature: str, command: Optional[str], success: bool, duration_ms: Optional[int],
                     error_type: Optional[str] = None) -> None:
        if not self.active:
            return
        try:
            self.store.enqueue("event", {
                "event_id": str(uuid.uuid4()), "ts": _now_iso(), "feature": sanitize.feature_id(feature),
                "command": sanitize.command_id(command), "success": bool(success),
                "duration_ms": None if duration_ms is None else max(0, min(int(duration_ms), 3_600_000)),
                "error_type": None if success else sanitize.error_type_from(error_type or "UnknownError")})
        except Exception:  # noqa: BLE001 - telemetry must never break a command
            logger.debug("telemetry record_usage failed", exc_info=True)

    def record_error(self, component: str, error, severity: str = "error") -> None:  # noqa: ANN001
        if not self.active:
            return
        try:
            self.store.enqueue("error", {
                "event_id": str(uuid.uuid4()), "ts": _now_iso(), "component": sanitize.component_id(component),
                "error_type": sanitize.error_type_from(error), "severity": sanitize.severity_id(severity)})
        except Exception:  # noqa: BLE001
            logger.debug("telemetry record_error failed", exc_info=True)

    # --------------------------------------------------------------------- sending --
    async def heartbeat(self) -> bool:
        if not self.active:
            return False
        reachable = None
        if self._reachability is not None:
            try:
                reachable = bool(await self._reachability())
            except Exception:  # noqa: BLE001
                reachable = None
        body: Dict[str, Any] = {"ts": _now_iso(), "device": hardware.collect(self.era_version)}
        if reachable is not None:
            body["agent_reachable"] = reachable
        return await self._send("/api/device/heartbeat", body)

    async def _send(self, path: str, body: Dict[str, Any]) -> bool:
        """True = delivered (or permanently rejected, so it should be dropped); False = retry later."""
        if self.store.flag("needs_reenroll") and time.time() < self._next_probe:
            return False  # server said "not recognised" recently: don't hammer it
        try:
            r = await self._signed_post(path, body)
        except (httpx.HTTPError, TelemetryError) as exc:
            self.last_error = f"{type(exc).__name__}"
            return False
        if r.status_code == 200:
            self.last_error = None
            if self.store.flag("needs_reenroll"):  # an administrator restored the device: carry on automatically
                self.store.set_flag("needs_reenroll", False)
            # Renew authorization lease for 15 minutes (900 seconds)
            self.store.save_lease("ACTIVE", time.time() + 900.0)
            return True
        if r.status_code == 401:
            # Revoked by an admin, account suspended, erased, or key rotated.
            # Immediately invalidate local authorization lease:
            self.store.invalidate_lease(status="REVOKED", reason="Revoked or suspended by Central")
            self.store.set_flag("needs_reenroll", True)
            self._next_probe = time.time() + max(self.heartbeat_seconds, 60)
            self.last_error = "device_not_recognised"
            return False
        if r.status_code in (429, 500, 502, 503, 504):
            self.last_error = f"http_{r.status_code}"
            return False
        self.last_error = f"rejected_{r.status_code}"
        return True  # 4xx (validation / 413...): resending the same data can never succeed -> drop it

    async def flush(self) -> Dict[str, int]:
        sent = {"events": 0, "errors": 0}
        if self.store.flag("pending_unenroll"):
            await self._try_unenroll()
        if not self.active:
            return sent
        for kind, path, key, name in (("event", "/api/device/events", "events", "events"),
                                      ("error", "/api/device/errors", "errors", "errors")):
            while True:
                rows = self.store.peek(kind, self.batch_size)
                if not rows:
                    break
                ok = await self._send(path, {key: [p for _, p in rows]})
                if not ok:
                    return sent
                self.store.delete([s for s, _ in rows])
                sent[name] += len(rows)
        return sent

    # ------------------------------------------------------------------ lifecycle --
    def start(self) -> None:
        if not self._tasks:
            self._tasks = [asyncio.create_task(self._loop(self.heartbeat, self.heartbeat_seconds)),
                           asyncio.create_task(self._loop(self.flush, self.flush_seconds))]

    async def _loop(self, fn: Callable[[], Awaitable[Any]], interval: int) -> None:
        while True:
            try:
                await fn()
                self._fail_count = 0 if not self.last_error else min(self._fail_count + 1, 6)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.debug("telemetry loop error", exc_info=True)
            await asyncio.sleep(min(interval * (2 ** self._fail_count), 900))
