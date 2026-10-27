"""Unit tests for core/session_store.py (same pattern as Local Agent V2)."""

from core.session_store import SessionStore


def test_save_and_get_roundtrip(tmp_path):
    store = SessionStore(db_path=tmp_path / "test.db")
    session_id = store.new_session_id()
    store.save(session_id, {"command": "open_notepad", "params": {}})
    assert store.get(session_id) == {"command": "open_notepad", "params": {}}


def test_get_missing_session_returns_none(tmp_path):
    store = SessionStore(db_path=tmp_path / "test.db")
    assert store.get("does-not-exist") is None


def test_delete_removes_session(tmp_path):
    store = SessionStore(db_path=tmp_path / "test.db")
    session_id = store.new_session_id()
    store.save(session_id, {"command": "x", "params": {}})
    store.delete(session_id)
    assert store.get(session_id) is None
