"""ERA Intelligence Core — Personal Vault.

Local-first secure store for sensitive data.
Sensitive documents stay local and are NEVER forwarded to cloud models
unless the user explicitly permits it for a specific operation.

Encryption: uses cryptography.fernet (already in .venv).
Storage: encrypted JSON lines in a local file.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


def _derive_key(password: str) -> bytes:
    """Derive a Fernet-compatible 32-byte key from a password using PBKDF2."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    import hashlib

    # Use a fixed salt stored alongside vault (not ideal for prod, but honest)
    salt = b"era_vault_salt_v1"
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
    key_bytes = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(key_bytes)


class PersonalVault:
    """Encrypted local-first store for sensitive data.

    Items stored:
        {id, label, category, encrypted_data, created_at, allow_cloud: bool}

    allow_cloud defaults to False. Cloud access requires explicit `allow_cloud=True`
    set by the user per item.
    """

    def __init__(self, vault_path: str, password: Optional[str] = None) -> None:
        self._path = Path(vault_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Use provided password or fall back to env var
        _password = password or os.getenv("ERA_VAULT_PASSWORD", "era_default_insecure_key_change_me")
        self._key = _derive_key(_password)

        try:
            from cryptography.fernet import Fernet
            self._fernet = Fernet(self._key)
        except ImportError:
            self._fernet = None

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def store(
        self,
        label: str,
        data: Any,
        category: str = "general",
        allow_cloud: bool = False,
    ) -> str:
        """Encrypt and store a piece of data. Returns item_id."""
        item_id = uuid.uuid4().hex
        serialized = json.dumps(data, ensure_ascii=False, default=str)
        encrypted = self._encrypt(serialized)

        import time
        entry = {
            "id": item_id,
            "label": label,
            "category": category,
            "allow_cloud": allow_cloud,
            "created_at": time.time(),
            "data": encrypted,
        }

        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

        return item_id

    def retrieve(self, item_id: str, allow_cloud_check: bool = False) -> Optional[Dict[str, Any]]:
        """Retrieve and decrypt an item by id.

        If allow_cloud_check is True and item.allow_cloud is False, raises PermissionError.
        """
        entry = self._find(item_id)
        if not entry:
            return None

        if allow_cloud_check and not entry.get("allow_cloud", False):
            raise PermissionError(
                f"Vault item '{entry['label']}' is marked local-only. "
                "Cannot send to cloud model without explicit user permission."
            )

        decrypted_str = self._decrypt(entry["data"])
        return {
            "id": entry["id"],
            "label": entry["label"],
            "category": entry["category"],
            "allow_cloud": entry["allow_cloud"],
            "created_at": entry["created_at"],
            "data": json.loads(decrypted_str),
        }

    def list_items(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List metadata (no data) for all vault items."""
        items = []
        for entry in self._read_all():
            if category and entry.get("category") != category:
                continue
            items.append({
                "id": entry["id"],
                "label": entry["label"],
                "category": entry["category"],
                "allow_cloud": entry["allow_cloud"],
                "created_at": entry["created_at"],
            })
        return items

    def delete(self, item_id: str) -> bool:
        """Delete an item from the vault."""
        all_entries = self._read_all()
        remaining = [e for e in all_entries if e.get("id") != item_id]
        if len(remaining) == len(all_entries):
            return False  # not found

        with self._lock:
            with self._path.open("w", encoding="utf-8") as f:
                for entry in remaining:
                    f.write(json.dumps(entry) + "\n")
        return True

    def set_allow_cloud(self, item_id: str, allow: bool) -> bool:
        """Update the allow_cloud flag for an item."""
        all_entries = self._read_all()
        modified = False
        for entry in all_entries:
            if entry.get("id") == item_id:
                entry["allow_cloud"] = allow
                modified = True
                break
        if not modified:
            return False

        with self._lock:
            with self._path.open("w", encoding="utf-8") as f:
                for entry in all_entries:
                    f.write(json.dumps(entry) + "\n")
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encrypt(self, plaintext: str) -> str:
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        # Fallback: base64 (NOT secure — but honest, not silent)
        return "b64:" + base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")

    def _decrypt(self, ciphertext: str) -> str:
        if ciphertext.startswith("b64:"):
            return base64.b64decode(ciphertext[4:]).decode("utf-8")
        if self._fernet:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        raise ValueError("Cannot decrypt: no Fernet key and not base64")

    def _read_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return entries

    def _find(self, item_id: str) -> Optional[Dict[str, Any]]:
        for entry in self._read_all():
            if entry.get("id") == item_id:
                return entry
        return None
