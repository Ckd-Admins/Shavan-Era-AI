"""Security regression tests for Era Bridge (Phase 2 hardening)."""
from __future__ import annotations

import logging
import platform
import stat

import pytest
from fastapi.testclient import TestClient

import bridge_server
from config import secrets_store, settings
from core import auth
from core.session_store import SessionStore

H = {"X-Era-Bridge-Key": settings.BRIDGE_API_KEY}


def _client(host="127.0.0.1", peer=("127.0.0.1", 50000)):
    return TestClient(bridge_server.app, base_url=f"http://{host}:8100", client=peer)


# ---- constant-time auth -------------------------------------------------
def test_auth_uses_constant_time_compare(monkeypatch):
    calls = []
    real = auth.secrets.compare_digest
    monkeypatch.setattr(auth.secrets, "compare_digest", lambda a, b: (calls.append(1), real(a, b))[1])
    assert auth.keys_match(settings.BRIDGE_API_KEY, settings.BRIDGE_API_KEY)
    assert not auth.keys_match("x", settings.BRIDGE_API_KEY)
    assert calls


def test_auth_rejects_missing_empty_wrong_and_non_ascii():
    c = _client()
    assert c.get("/v1/commands").status_code == 401
    assert c.get("/v1/commands", headers={"X-Era-Bridge-Key": ""}).status_code == 401
    assert c.get("/v1/commands", headers={"X-Era-Bridge-Key": "wrong"}).status_code == 401
    assert c.get("/v1/commands", headers=H).status_code == 200
    assert not auth.keys_match("é", settings.BRIDGE_API_KEY)


# ---- key is never logged; persisted with owner-only perms ---------------
def test_api_key_never_logged(caplog):
    with caplog.at_level(logging.DEBUG):
        _client().get("/v1/commands", headers=H)
        _client().get("/v1/commands", headers={"X-Era-Bridge-Key": "wrong-key-value"})
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert settings.BRIDGE_API_KEY not in text and "wrong-key-value" not in text


def test_no_source_logs_the_key():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    for path in root.rglob("*.py"):
        if "tests" in path.parts or "venv" in path.parts:
            continue
        src = path.read_text(encoding="utf-8")
        assert "_API_KEY_WAS_GENERATED" not in src, path


def test_generated_key_is_persisted_stable_and_owner_only(tmp_path, monkeypatch):
    monkeypatch.delenv("SOME_KEY_ENV", raising=False)
    monkeypatch.setenv("ERA_HOME", str(tmp_path))
    first = secrets_store.load_or_create_key("SOME_KEY_ENV", "k.key")
    assert first == secrets_store.load_or_create_key("SOME_KEY_ENV", "k.key") and len(first) >= 32
    key_file = tmp_path / "k.key"
    if platform.system() == "Windows":
        import win32security
        sd = win32security.GetFileSecurity(str(key_file), win32security.DACL_SECURITY_INFORMATION)
        dacl = sd.GetSecurityDescriptorDacl()
        assert dacl is not None and dacl.GetAceCount() >= 1
    else:
        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    monkeypatch.setenv("SOME_KEY_ENV", "from-env")
    assert secrets_store.load_or_create_key("SOME_KEY_ENV", "k.key") == "from-env"


# ---- status endpoint ----------------------------------------------------
def test_health_public_status_private():
    c = _client()
    assert c.get("/v1/health").json() == {"status": "ok"}
    assert c.get("/v1/status").status_code == 401


# ---- CORS + host allowlist ----------------------------------------------
def test_cors_not_wildcard_and_foreign_origin_denied():
    c = _client()
    pre = c.options("/v1/execute", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert pre.headers.get("access-control-allow-origin") not in ("*", "https://evil.example")
    ok = c.options("/v1/execute", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                                            "Access-Control-Request-Headers": "x-era-bridge-key,content-type"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad_hdr = c.options("/v1/execute", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                                                 "Access-Control-Request-Headers": "x-evil"})
    assert bad_hdr.status_code == 400


def test_dns_rebinding_host_rejected():
    assert _client(host="evil.example").get("/v1/health").status_code == 400


# ---- memory local-only: fail closed behind proxies ----------------------
@pytest.mark.parametrize("hdr", ["X-Forwarded-For", "Forwarded", "X-Real-IP", "X-Forwarded-Host"])
def test_memory_refuses_forwarded_requests_even_from_loopback_peer(hdr):
    r = _client().get("/v1/memory", headers={**H, hdr: "203.0.113.9"})
    assert r.status_code == 403


def test_memory_allows_plain_loopback():
    assert _client().get("/v1/memory/settings", headers=H).status_code == 200


def test_memory_refuses_non_loopback_peer_and_testclient_sentinel():
    assert _client(peer=("203.0.113.9", 1)).get("/v1/memory", headers=H).status_code == 403
    assert _client(peer=("testclient", 1)).get("/v1/memory", headers=H).status_code == 403


# ---- session expiry -----------------------------------------------------
def test_expired_sessions_are_invisible_and_pruned(tmp_path):
    store = SessionStore(db_path=tmp_path / "s.db", ttl_seconds=1)
    sid = store.new_session_id()
    store.save(sid, {"command": "open_notepad", "params": {}})
    assert store.get(sid) is not None
    with store._connect() as conn:
        conn.execute("UPDATE sessions SET updated_at = datetime('now', '-2 seconds')")
    assert store.get(sid) is None
    assert store.prune_expired() == 1
    assert store.prune_expired() == 0


def test_save_refreshes_ttl_and_prunes_other_stale_rows(tmp_path):
    store = SessionStore(db_path=tmp_path / "s.db", ttl_seconds=60)
    old, new = store.new_session_id(), store.new_session_id()
    store.save(old, {"command": "a"})
    with store._connect() as conn:
        conn.execute("UPDATE sessions SET updated_at = datetime('now', '-2 minutes') WHERE session_id = ?", (old,))
    store.save(new, {"command": "b"})
    with store._connect() as conn:
        ids = [r[0] for r in conn.execute("SELECT session_id FROM sessions")]
    assert ids == [new]


def test_expired_session_confirm_returns_404(tmp_path):
    bridge_server.session_store = SessionStore(db_path=tmp_path / "s.db", ttl_seconds=1)
    r = _client().post("/v1/confirm", headers=H, json={"session_id": "gone", "confirmed": True})
    assert r.status_code == 404
