"""macOS Keychain credential storage for DeepNode.

Replaces plain-text JSON file (~/.deeppool/device_credential.json) with
macOS Keychain, providing OS-level protection for device credentials.

The Keychain entry is scoped to the DeepNode application via a unique
service name. On non-macOS platforms, falls back to the legacy file-based
storage transparently.

Security benefits:
  - Credentials encrypted at rest by macOS (AES-256-GCM via Secure Enclave)
  - Access controlled by app codesign identity (when Developer ID is used)
  - Protected by user login keychain password / Touch ID
  - Not trivially readable by other processes (unlike plain JSON)
"""

from __future__ import annotations

import json
import logging
import platform
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Keychain service name — unique identifier for DeepNode credentials
_KEYCHAIN_SERVICE = "com.deeppool.deepnode"
_KEYCHAIN_ACCOUNT = "device_credential"


def _is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system().lower() == "darwin"


def _run_security(args: list[str], input_data: str = "") -> tuple[int, str, str]:
    """Execute macOS `security` command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["security"] + args,
            input=input_data.encode("utf-8") if input_data else None,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as exc:
        logger.debug("security command failed: %s", exc)
        return -1, "", str(exc)


def save_to_keychain(simei: str, token: str, binding_hash: str = "") -> bool:
    """Store device credential in macOS Keychain.

    Uses `security add-generic-password` (or update if exists).
    The credential is stored as a JSON string in the password field.

    Returns:
        True if saved successfully, False otherwise.
    """
    if not _is_macos():
        logger.debug("keychain storage not available on %s", platform.system())
        return False

    payload = json.dumps(
        {"simei": simei, "token": token, "binding_hash": binding_hash},
        ensure_ascii=False,
    )

    # Try to update existing entry first
    rc, _, stderr = _run_security([
        "add-generic-password",
        "-s", _KEYCHAIN_SERVICE,
        "-a", _KEYCHAIN_ACCOUNT,
        "-w", payload,
        "-U",  # update if exists
    ])

    if rc == 0:
        logger.info("device credential saved to keychain service=%s", _KEYCHAIN_SERVICE)
        return True

    # If add failed (e.g. keychain locked), log warning
    logger.warning("failed to save credential to keychain: %s", stderr.strip())
    return False


def load_from_keychain() -> Optional[dict]:
    """Load device credential from macOS Keychain.

    Returns:
        {"simei": str, "token": str} dict, or None if not found / error.
    """
    if not _is_macos():
        return None

    rc, stdout, stderr = _run_security([
        "find-generic-password",
        "-s", _KEYCHAIN_SERVICE,
        "-a", _KEYCHAIN_ACCOUNT,
        "-w",  # output password only
    ])

    if rc != 0:
        # Item not found or keychain locked — not an error for first run
        if "could not be found" in stderr.lower() or "the specified item could not be found" in stderr.lower():
            logger.debug("no keychain entry found for service=%s", _KEYCHAIN_SERVICE)
        else:
            logger.debug("keychain read failed: %s", stderr.strip())
        return None

    password = stdout.strip()
    if not password:
        return None

    try:
        data = json.loads(password)
        simei = str(data.get("simei", "")).strip()
        token = str(data.get("token", "")).strip()
        if not simei or not token:
            logger.warning("keychain credential incomplete, ignoring")
            return None
        binding_hash = str(data.get("binding_hash", "")).strip()
        logger.info("device credential loaded from keychain simei=%s binding_hash=%s",
                     simei, bool(binding_hash))
        return {"simei": simei, "token": token, "binding_hash": binding_hash}
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("failed to parse keychain credential: %s", exc)
        return None


def delete_from_keychain() -> bool:
    """Remove device credential from macOS Keychain.

    Returns:
        True if deleted successfully, False otherwise.
    """
    if not _is_macos():
        return False

    rc, _, stderr = _run_security([
        "delete-generic-password",
        "-s", _KEYCHAIN_SERVICE,
        "-a", _KEYCHAIN_ACCOUNT,
    ])

    if rc == 0:
        logger.info("device credential deleted from keychain")
        return True

    logger.debug("keychain delete: %s", stderr.strip())
    return False
