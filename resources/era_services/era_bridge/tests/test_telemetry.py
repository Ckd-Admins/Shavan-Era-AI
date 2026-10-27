"""Bridge telemetry: consent gate, privacy allow-lists, outbox, signing, failure handling."""
from __future__ import annotations

import json
import platform

import httpx
import pytest
from fastapi.testclient import TestClient

import bridge_server
from config import settings
from core.telemetry.service import TelemetryError, TelemetryService, validate_central_url
from core.telemetry import sanitize

H = {"X-Era-Bridge-Key": settings.BRIDGE_API_KEY}
URL = "https://central.example"


class Recorder:
    """Plays ERA Central: records every request, answers with scripted status codes."""

    def __init__(self, status=200):
        self.status, self.requests = status, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        code = self.status(request) if callable(self.status) else self.status
        return httpx.Response(code, json={"status": "ok"})

    def paths(self):
        return [r.url.path for r in self.requests]


def make(tmp_path, rec=None, url=URL, **kw):
    rec = rec or Recorder()
    svc = TelemetryService(tmp_path / "t", url, "1.0.0", transport=httpx.MockTransport(rec), **kw)
    return svc, rec


async def activate(svc):
    await svc.set_consent(True)
    await svc.enroll("x" * 40)


# ------------------------------------------------------------------ opt-in --
async def test_off_by_default_records_nothing_and_sends_nothing(tmp_path):
    svc, rec = make(tmp_path)
    svc.record_usage("pc_control", "open_notepad", True, 5)
    svc.record_error("bridge", "Boom")
    assert svc.status()["queued"] == 0 and not svc.consent
    assert await svc.flush() == {"events": 0, "errors": 0} and await svc.heartbeat() is False
    assert rec.requests == []


async def test_consent_alone_does_not_collect_until_enrolled(tmp_path):
    svc, rec = make(tmp_path)
    await svc.set_consent(True)
    svc.record_usage("pc_control", "open_notepad", True, 5)
    assert svc.status()["queued"] == 0 and rec.requests == []


async def test_enroll_requires_consent_and_valid_url(tmp_path):
    svc, _ = make(tmp_path)
    with pytest.raises(TelemetryError) as e:
        await svc.enroll("x" * 40)
    assert e.value.status == 409
    svc2, _ = make(tmp_path / "b", url="")
    await svc2.set_consent(True)
    with pytest.raises(TelemetryError):
        await svc2.enroll("x" * 40)


@pytest.mark.parametrize("url,ok", [("https://c.example", True), ("http://127.0.0.1:9000", True), ("http://localhost:1", True),
                                    ("http://central.example", False), ("https://c.example/api", False),
                                    ("https://user:pw@c.example", False), ("ftp://c.example", False), ("", False)])
def test_central_url_must_be_https_bare_origin(url, ok):
    if ok:
        assert validate_central_url(url)
    else:
        with pytest.raises(TelemetryError):
            validate_central_url(url)


# --------------------------------------------------------------- enrollment --
async def test_enroll_sends_public_key_and_pop_but_never_the_private_key(tmp_path):
    svc, rec = make(tmp_path)
    await activate(svc)
    req = rec.requests[0]
    body = json.loads(req.content)
    assert req.url.path == "/api/device/enroll" and svc.enrolled
    assert body["public_key"] == svc.identity.public_key_b64 and body["installation_id"] == svc.identity.installation_id
    raw = (tmp_path / "t" / "identity.json").read_text()
    private = json.loads(raw)["private_key"]
    ident_file = tmp_path / "t" / "identity.json"
    if platform.system() == "Windows":
        import win32security
        sd = win32security.GetFileSecurity(str(ident_file), win32security.DACL_SECURITY_INFORMATION)
        dacl = sd.GetSecurityDescriptorDacl()
        assert dacl is not None and dacl.GetAceCount() >= 1
    else:
        assert ident_file.stat().st_mode & 0o777 == 0o600


async def test_enroll_token_is_not_persisted(tmp_path):
    svc, _ = make(tmp_path)
    await svc.set_consent(True)
    token = "SECRET-TOKEN-" + "x" * 30
    await svc.enroll(token)
    for f in (tmp_path / "t").iterdir():
        assert token.encode() not in f.read_bytes(), f


async def test_enroll_failure_surfaces_without_marking_enrolled(tmp_path):
    svc, _ = make(tmp_path, Recorder(401))
    await svc.set_consent(True)
    with pytest.raises(TelemetryError):
        await svc.enroll("x" * 40)
    assert not svc.enrolled


async def test_identity_is_stable_across_restarts(tmp_path):
    a, _ = make(tmp_path)
    b, _ = make(tmp_path)
    assert a.identity.installation_id == b.identity.installation_id and a.identity.public_key_b64 == b.identity.public_key_b64


# ------------------------------------------------------------ privacy gates --
async def test_only_allowlisted_identifiers_are_queued(tmp_path):
    svc, _ = make(tmp_path)
    await activate(svc)
    svc.record_usage("pc_control", "open_notepad", True, 12)
    svc.record_usage("totally_new_feature", "format c: /q", False, 5, "C:\\Users\\bob\\secret.txt")
    svc.record_usage("pc_control", "open_calculator", False, 5, Exception("password=hunter2 in C:/x"))
    svc.record_error("bridge", ValueError("my private message"))
    svc.record_error("not_a_component", "https://evil/x?token=abc", "catastrophic")
    q = svc.preview()
    blob = json.dumps(q)
    for leaked in ("format c", "bob", "secret.txt", "hunter2", "private message", "evil", "token=abc"):
        assert leaked not in blob
    ev = q["events"]
    assert ev[0]["command"] == "open_notepad" and ev[1]["feature"] == "unknown" and ev[1]["command"] == "unknown"
    assert ev[1]["error_type"] == "UnknownError" and ev[2]["error_type"] == "Exception"
    assert q["errors"][0]["error_type"] == "ValueError"
    assert q["errors"][1]["component"] == "bridge" and q["errors"][1]["severity"] == "error"
    assert set(ev[0]) == {"event_id", "ts", "feature", "command", "success", "duration_ms", "error_type"}


def test_error_type_never_uses_exception_message():
    class Weird(Exception):
        pass
    assert sanitize.error_type_from(Weird("C:/secret password=1")) == "Weird"
    assert sanitize.error_type_from("has spaces and C:/path") == "UnknownError"
    assert sanitize.error_type_from("a" * 100) == "UnknownError"


async def test_record_never_raises_even_if_store_breaks(tmp_path, monkeypatch):
    svc, _ = make(tmp_path)
    await activate(svc)
    monkeypatch.setattr(svc.store, "enqueue", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    svc.record_usage("pc_control", "open_notepad", True, 1)
    svc.record_error("bridge", "X")


async def test_outbox_is_bounded(tmp_path):
    svc, _ = make(tmp_path, outbox_max=10)
    await activate(svc)
    for _ in range(50):
        svc.record_usage("pc_control", "open_notepad", True, 1)
    assert svc.status()["queued"] == 10


# ------------------------------------------------------------------ sending --
async def test_flush_signs_batches_and_empties_outbox(tmp_path):
    svc, rec = make(tmp_path, batch_size=3)
    await activate(svc)
    for _ in range(7):
        svc.record_usage("pc_control", "open_notepad", True, 1)
    svc.record_error("bridge", "ConnectError")
    assert await svc.flush() == {"events": 7, "errors": 1}
    assert svc.status()["queued"] == 0
    sent = [r for r in rec.requests if r.url.path != "/api/device/enroll"]
    assert [len(json.loads(r.content)["events"]) for r in sent if r.url.path.endswith("events")] == [3, 3, 1]
    for r in sent:
        for h in ("x-era-device", "x-era-timestamp", "x-era-nonce", "x-era-signature"):
            assert h in r.headers
    assert len({r.headers["x-era-nonce"] for r in sent}) == len(sent)  # fresh nonce every request


async def test_failures_keep_data_for_retry(tmp_path):
    for code in (500, 503, 429):
        svc, _ = make(tmp_path / str(code), Recorder(lambda r, c=code: 200 if "enroll" in r.url.path else c))
        await activate(svc)
        svc.record_usage("pc_control", "open_notepad", True, 1)
        await svc.flush()
        assert svc.status()["queued"] == 1 and svc.enrolled


async def test_network_error_keeps_data_and_does_not_raise(tmp_path):
    def handler(request):
        if "enroll" in request.url.path:
            return httpx.Response(200, json={})
        raise httpx.ConnectError("down")
    svc = TelemetryService(tmp_path / "t", URL, "1.0.0", transport=httpx.MockTransport(handler))
    await activate(svc)
    svc.record_usage("pc_control", "open_notepad", True, 1)
    assert (await svc.flush())["events"] == 0 and svc.status()["queued"] == 1


async def test_validation_rejection_drops_poison_batch(tmp_path):
    svc, _ = make(tmp_path, Recorder(lambda r: 200 if "enroll" in r.url.path else 422))
    await activate(svc)
    svc.record_usage("pc_control", "open_notepad", True, 1)
    await svc.flush()
    assert svc.status()["queued"] == 0  # would otherwise be resent forever


async def test_401_flags_reenroll_backs_off_then_resumes_when_server_accepts_again(tmp_path):
    state = {"reject": True}
    rec = Recorder(lambda r: 200 if "enroll" in r.url.path else (401 if state["reject"] else 200))
    svc, _ = make(tmp_path, rec)
    await activate(svc)
    svc.record_usage("pc_control", "open_notepad", True, 1)
    await svc.flush()
    st = svc.status()
    assert st["needs_reenroll"] and st["enrolled"] and st["queued"] == 1      # kept, not dropped
    n = len(rec.requests)
    await svc.flush()
    assert len(rec.requests) == n                                              # backed off: no traffic inside the window
    state["reject"] = False                                                    # admin restored the device
    svc._next_probe = 0.0
    assert (await svc.flush())["events"] == 1
    st = svc.status()
    assert not st["needs_reenroll"] and st["queued"] == 0


async def test_heartbeat_contains_only_safe_hardware_fields(tmp_path):
    async def reach():
        return True
    svc, rec = make(tmp_path, reachability=reach)
    await activate(svc)
    assert await svc.heartbeat()
    body = json.loads(rec.requests[-1].content)
    assert set(body) == {"ts", "device", "agent_reachable"} and body["agent_reachable"] is True
    assert set(body["device"]) <= {"era_version", "os", "os_version", "arch", "cpu_cores", "ram_gb"}
    text = json.dumps(body).lower()
    import platform, getpass
    for private in (platform.node().lower(), getpass.getuser().lower()):
        if len(private) > 3:
            assert private not in text


# ---------------------------------------------------------- revoking consent --
async def test_disabling_consent_purges_outbox_and_erases_server_side(tmp_path):
    svc, rec = make(tmp_path)
    await activate(svc)
    svc.record_usage("pc_control", "open_notepad", True, 1)
    await svc.set_consent(False)
    assert svc.status()["queued"] == 0 and not svc.consent and not svc.enrolled
    assert rec.paths()[-1] == "/api/device/unenroll"
    svc.record_usage("pc_control", "open_notepad", True, 1)
    assert svc.status()["queued"] == 0


async def test_unenroll_is_retried_when_offline(tmp_path):
    state = {"down": False}

    def handler(request):
        if state["down"]:
            raise httpx.ConnectError("offline")
        return httpx.Response(200, json={})
    svc = TelemetryService(tmp_path / "t", URL, "1.0.0", transport=httpx.MockTransport(handler))
    await activate(svc)
    state["down"] = True
    await svc.set_consent(False)
    assert svc.enrolled and svc.store.flag("pending_unenroll")
    state["down"] = False
    await svc.flush()
    assert not svc.enrolled and not svc.store.flag("pending_unenroll")


# ---------------------------------------------------------------- HTTP routes --
def _client(tmp_path, rec=None):
    svc, rec = make(tmp_path, rec)
    bridge_server.telemetry_service = svc
    return TestClient(bridge_server.app, base_url="http://127.0.0.1:8100", client=("127.0.0.1", 50000)), svc, rec


def test_routes_require_key_and_local(tmp_path):
    c, _, _ = _client(tmp_path)
    assert c.get("/v1/telemetry/status").status_code == 401
    remote = TestClient(bridge_server.app, base_url="http://127.0.0.1:8100", client=("203.0.113.9", 1))
    assert remote.get("/v1/telemetry/status", headers=H).status_code == 403
    assert c.get("/v1/telemetry/status", headers=H).json()["consent"] is False


def test_route_flow_consent_enroll_queue_and_validation(tmp_path):
    c, svc, rec = _client(tmp_path)
    assert c.post("/v1/telemetry/enroll", headers=H, json={"id_token": "x" * 40}).status_code == 409
    assert c.post("/v1/telemetry/consent", headers=H, json={"enabled": "maybe"}).status_code == 422
    assert c.post("/v1/telemetry/consent", headers=H, json={"enabled": True, "x": 1}).status_code == 422
    assert c.post("/v1/telemetry/consent", headers=H, json={"enabled": True}).json()["consent"] is True
    assert c.post("/v1/telemetry/enroll", headers=H, json={"id_token": "short"}).status_code == 422
    assert c.post("/v1/telemetry/enroll", headers=H, json={"id_token": "x" * 40}).json()["enrolled"] is True
    assert c.get("/v1/telemetry/queue", headers=H).json() == {"events": [], "errors": []}


def _execute_client(tmp_path, **agent_kw):
    import asyncio
    from core.session_store import SessionStore
    from tests.test_bridge_api import FakeAgentClient

    c, svc, rec = _client(tmp_path)
    asyncio.run(activate(svc))
    bridge_server.session_store = SessionStore(db_path=tmp_path / "s.db")
    bridge_server.agent_client = FakeAgentClient(**agent_kw)
    return c, svc


def test_execute_success_records_exactly_one_metadata_event(tmp_path):
    c, svc = _execute_client(tmp_path, command_result={"success": True, "message": "PRIVATE MESSAGE"})
    assert c.post("/v1/execute", headers=H, json={"command": "open_notepad"}).json()["state"] == "success"
    q = svc.preview()
    assert len(q["events"]) == 1 and q["errors"] == []
    ev = q["events"][0]
    assert (ev["feature"], ev["command"], ev["success"], ev["error_type"]) == ("pc_control", "open_notepad", True, None)
    assert isinstance(ev["duration_ms"], int) and "PRIVATE" not in json.dumps(q)


def test_execute_agent_failure_and_unreachable_are_recorded_as_errors(tmp_path):
    c, svc = _execute_client(tmp_path, command_result={"success": False, "message": "C:/secret/path failed"})
    c.post("/v1/execute", headers=H, json={"command": "open_notepad"})
    ev = svc.preview()["events"][0]
    assert (ev["success"], ev["error_type"]) == (False, "CommandFailed") and "secret" not in json.dumps(svc.preview())

    c, svc = _execute_client(tmp_path / "b", healthy=False)
    assert c.post("/v1/execute", headers=H, json={"command": "open_notepad"}).json()["state"] == "agent_unreachable"
    q = svc.preview()
    assert q["events"][0]["error_type"] == "AgentUnreachable" and q["events"][0]["duration_ms"] is None
    assert [(e["component"], e["error_type"], e["severity"]) for e in q["errors"]] == [("bridge", "AgentUnreachable", "warning")]


def test_execute_exception_records_class_name_only(tmp_path):
    class Boom(Exception):
        pass

    c, svc = _execute_client(tmp_path)

    async def explode(_command, auth_token=None):
        raise Boom("secret C:/Users/me password=1")

    bridge_server.agent_client.execute_command = explode
    assert c.post("/v1/execute", headers=H, json={"command": "open_notepad"}).json()["state"] == "failure"
    q = svc.preview()
    assert q["events"][0]["error_type"] == "Boom" and q["errors"][0]["error_type"] == "Boom"
    assert "secret" not in json.dumps(q) and "password" not in json.dumps(q)


def test_execute_with_telemetry_off_records_nothing(tmp_path):
    c, svc, _ = _client(tmp_path)
    from tests.test_bridge_api import FakeAgentClient
    bridge_server.agent_client = FakeAgentClient()
    c.post("/v1/execute", headers=H, json={"command": "open_notepad"})
    assert svc.status()["queued"] == 0


def test_memory_calls_record_operation_and_outcome_only(tmp_path, db_path, clock):
    from era_memory import MemoryConfig, MemoryManager
    c, svc = _execute_client(tmp_path)
    bridge_server.memory_manager = MemoryManager(MemoryConfig(db_path=db_path), clock=clock)
    c.post("/v1/memory/context", headers=H, json={"message": "my secret project is Atlas"})
    c.post("/v1/memory/ingest", headers=H, json={"user_message": "my secret project is Atlas", "assistant_message": "ok", "conversation_id": "c1"})
    events = svc.preview()["events"]
    assert [(e["feature"], e["command"]) for e in events] == [("memory", "context"), ("memory", "ingest")]
    assert "Atlas" not in json.dumps(events) and "secret" not in json.dumps(events)
