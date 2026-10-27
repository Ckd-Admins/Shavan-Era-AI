"""Persistent local secrets for Era Bridge (never logged).

``load_or_create_key`` resolves a secret from an environment variable, or
else from an owner-only file under ``ERA_HOME`` (default ``~/.era``),
creating it atomically with a random value on first use. On Windows,
NTFS DACLs are set to restrict access strictly to the owner.
"""

from __future__ import annotations

import os
import platform
import secrets
from pathlib import Path


def era_home() -> Path:
    return Path(os.environ.get("ERA_HOME") or (Path.home() / ".era"))


def set_owner_only_permissions(path: Path) -> None:
    """Restricts file permissions to current owner only on both POSIX and Windows."""
    if platform.system() == "Windows":
        try:
            import win32security
            import ntsecuritycon

            user, domain, _ = win32security.LookupAccountName("", os.getlogin())
            sd = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
            dacl = win32security.ACL()
            dacl.AddAccessAllowedAce(win32security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, user)
            # Set protected DACL (prevents inheritance from parent folder)
            sd.SetSecurityDescriptorDacl(1, dacl, 1)
            win32security.SetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION, sd)
        except Exception:
            # Fallback if win32security not available
            pass
    else:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def load_or_create_key(env_var: str, file_name: str) -> str:
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value
    path = era_home() / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_text(encoding="utf-8").strip()
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(secrets.token_urlsafe(32))
    set_owner_only_permissions(path)
    return path.read_text(encoding="utf-8").strip()
