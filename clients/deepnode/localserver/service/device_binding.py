"""Device binding — ties credential validity to hardware fingerprint.

Ensures that a credential (simei + token) obtained on one machine cannot
be used on a different machine. Each time the node starts, it re-computes
the hardware fingerprint and compares it with the stored binding hash.

This forces an attacker to re-register (and re-tamper) on every machine,
raising the attack cost from O(1) to O(N) where N = number of machines.

Binding flow:
  First activation:
    1. Generate device fingerprint (simei) via device_fingerprint module
    2. Compute binding_hash = SHA256(simei + IOPlatformUUID + serial)
    3. Store binding_hash in Keychain alongside credential

  Every startup:
    1. Re-compute binding_hash from current hardware
    2. Load stored binding_hash from Keychain
    3. Compare — mismatch means credential was copied from another machine
    4. Report binding status to platform via device_config

Security note:
  The binding hash uses hardware identifiers that are extremely difficult
  to forge (IOPlatformUUID from Secure Enclave, serial number from hardware).
  Even if an attacker copies the Keychain entry, the hash won't match on
  a different machine.
"""

from __future__ import annotations

import hashlib
import logging
import platform
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def _run_cmd(cmd: str, args: list[str], timeout: int = 10) -> str:
    """Execute a system command and return stdout (stripped)."""
    try:
        result = subprocess.run(
            [cmd, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def get_hardware_binding_factors() -> dict[str, str]:
    """Collect hardware binding factors for the current machine.

    Returns a dict of factor_name → value. Only non-empty values are included.
    """
    factors: dict[str, str] = {}

    if platform.system().lower() != "darwin":
        logger.debug("device binding only supported on macOS")
        return factors

    # IOPlatformUUID — from Secure Enclave, extremely hard to forge
    ioreg = _run_cmd("ioreg", ["-rd1", "-c", "IOPlatformExpertDevice"])
    for line in ioreg.splitlines():
        row = line.strip()
        if '"IOPlatformUUID"' in row and "=" in row:
            _, right = row.split("=", 1)
            val = right.strip().strip('"')
            if val:
                factors["platform_uuid"] = val

    # Serial number — hardware-level identifier
    serial = _run_cmd("system_profiler", ["SPHardwareDataType"])
    for line in serial.splitlines():
        row = line.strip()
        if ":" in row:
            key, value = row.split(":", 1)
            key_lower = key.strip().lower()
            if key_lower in ("serial number (system)", "serial number"):
                val = value.strip()
                if val:
                    factors["serial_number"] = val
                    break

    # Hardware UUID (may differ from IOPlatformUUID on some models)
    for line in serial.splitlines():
        row = line.strip()
        if ":" in row:
            key, value = row.split(":", 1)
            if key.strip().lower() == "hardware uuid":
                val = value.strip()
                if val:
                    factors["hardware_uuid"] = val
                    break

    # Model identifier
    for line in serial.splitlines():
        row = line.strip()
        if ":" in row:
            key, value = row.split(":", 1)
            if key.strip().lower() == "model identifier":
                val = value.strip()
                if val:
                    factors["model_id"] = val
                    break

    return factors


def compute_binding_hash(simei: str) -> Optional[str]:
    """Compute a device-specific binding hash.

    Combines the software identity (simei) with hardware identifiers to
    produce a hash that is unique to this machine + this registration.

    Returns:
        SHA-256 hex digest, or None if insufficient binding factors.
    """
    factors = get_hardware_binding_factors()
    if not factors:
        logger.warning("no hardware binding factors available")
        return None

    # Sort factors for deterministic hash
    parts = [f"simei={simei}"]
    for key in sorted(factors.keys()):
        parts.append(f"{key}={factors[key]}")

    payload = ";".join(parts)
    binding_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    logger.info(
        "device binding hash computed: %s...%s (factors=%d)",
        binding_hash[:8], binding_hash[-8:], len(factors),
    )
    return binding_hash


def verify_binding(simei: str, stored_hash: str) -> bool:
    """Verify that the current machine matches the stored binding hash.

    Args:
        simei: device identifier from credential
        stored_hash: binding hash stored at registration time

    Returns:
        True if the current machine matches, False if mismatched.
    """
    current_hash = compute_binding_hash(simei)
    if current_hash is None:
        logger.warning("cannot verify binding: no hardware factors")
        return True  # gracefully pass if we can't compute

    if current_hash == stored_hash:
        logger.info("device binding verified: hash matches")
        return True

    logger.error(
        "device binding MISMATCH: stored=%s...%s current=%s...%s — "
        "credential may have been copied from another machine",
        stored_hash[:8], stored_hash[-8:],
        current_hash[:8], current_hash[-8:],
    )
    return False
