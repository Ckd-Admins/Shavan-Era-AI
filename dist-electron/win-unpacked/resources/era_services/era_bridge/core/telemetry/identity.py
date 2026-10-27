"""Installation identity: a random installation id + an Ed25519 keypair generated ON this machine.

The private key never leaves the device (the server only ever receives the public key). It is stored
in an owner-only file. There is no shared device secret anywhere.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DeviceIdentity:
    def __init__(self, installation_id: str, private_key: Ed25519PrivateKey):
        self.installation_id = installation_id
        self._key = private_key
        self.public_key_b64 = _b64(private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw))

    # -- persistence ---------------------------------------------------------
    @classmethod
    def load_or_create(cls, directory: Path) -> "DeviceIdentity":
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "identity.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(data["private_key"]))
            return cls(data["installation_id"], key)
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        payload = json.dumps({"installation_id": str(uuid.uuid4()), "private_key": _b64(raw)})
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        from config.secrets_store import set_owner_only_permissions
        set_owner_only_permissions(path)
        return cls.load_or_create(directory)

    # -- signing (message formats must match era_central.security.device_auth) ----
    def sign(self, message: bytes) -> str:
        return _b64(self._key.sign(message))

    def enroll_message(self, timestamp: str, nonce: str, id_token: str) -> bytes:
        return "\n".join(["ERA-ENROLL-V1", self.installation_id, self.public_key_b64, timestamp, nonce,
                          sha256_hex(id_token.encode())]).encode()

    def request_message(self, method: str, path: str, timestamp: str, nonce: str, body: bytes) -> bytes:
        return "\n".join(["ERA-DEVICE-V1", method.upper(), path, timestamp, nonce, sha256_hex(body),
                          self.installation_id]).encode()
