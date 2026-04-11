"""Device credential persistence with Keychain-first strategy.

Storage priority:
  Save: Keychain (primary) + file (backup fallback)
  Load: Keychain first → file fallback → None

On macOS, credentials are stored in the system Keychain (encrypted, access-
controlled). The legacy JSON file is kept as a fallback for non-macOS
platforms and edge cases where Keychain access fails.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Legacy file-based storage path (fallback)
_CREDENTIAL_DIR = Path("~/.deeppool").expanduser()
_CREDENTIAL_FILE = _CREDENTIAL_DIR / "device_credential.json"


@dataclass
class DeviceCredential:
    """Device credential containing minimal info for platform authentication."""
    simei: str
    token: str
    binding_hash: str = ""  # hardware binding hash (empty = not bound yet)


def save_credential(cred: DeviceCredential) -> None:
    """Persist device credential using Keychain (primary) + file (fallback).

    Automatically computes and stores the device binding hash on first save.
    Attempts Keychain first. Always writes the file as backup to ensure
    reliability across system restarts and Keychain lock scenarios.
    """
    # Compute binding hash if not already set
    if not cred.binding_hash:
        try:
            from service.device_binding import compute_binding_hash
            bh = compute_binding_hash(cred.simei)
            if bh:
                cred.binding_hash = bh
                logger.info("device binding hash computed on first save")
                # Apply device-specific .pyc watermark on first activation.
                # This makes every device's .pyc files byte-different, preventing
                # cross-machine patch copying.
                _apply_pyc_watermark(bh)
        except Exception as exc:
            logger.debug("binding hash computation skipped: %s", exc)

    # Primary: macOS Keychain
    try:
        from service.keychain import save_to_keychain
        if save_to_keychain(cred.simei, cred.token, cred.binding_hash):
            logger.info("credential saved to keychain simei=%s", cred.simei)
        else:
            logger.debug("keychain save skipped (not macOS or failed)")
    except Exception as exc:
        logger.debug("keychain save error: %s", exc)

    # Fallback: file-based storage (with restrictive permissions)
    _CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _CREDENTIAL_DIR.chmod(0o700)
    except OSError:
        pass
    _CREDENTIAL_FILE.write_text(
        json.dumps(asdict(cred), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Restrict file permissions to owner-only (0600) to prevent other users
    # on the same machine from reading the credential.
    try:
        _CREDENTIAL_FILE.chmod(0o600)
    except OSError as exc:
        logger.debug("failed to set credential file permissions: %s", exc)
    logger.info("credential saved to file simei=%s", cred.simei)


def load_credential() -> DeviceCredential | None:
    """Load device credential: Keychain first, then file fallback.

    After loading, verifies the device binding hash to ensure the credential
    belongs to this machine. Returns None if binding check fails.
    """
    cred = _load_credential_raw()
    if cred is None:
        return None

    # Verify device binding (skip if no binding hash stored — legacy credential)
    if cred.binding_hash:
        try:
            from service.device_binding import verify_binding
            if not verify_binding(cred.simei, cred.binding_hash):
                logger.error(
                    "credential rejected: device binding mismatch simei=%s — "
                    "this credential was likely copied from another machine",
                    cred.simei,
                )
                return None
        except Exception as exc:
            logger.warning("device binding verification error (allowing): %s", exc)

        # Verify .pyc watermarks match this device (cross-machine copy detection)
        try:
            from service.pyc_watermark import verify_watermark
            if not verify_watermark(cred.binding_hash):
                logger.error(
                    "credential rejected: pyc watermark mismatch simei=%s — "
                    "mlx-packages/ files may have been copied from another device",
                    cred.simei,
                )
                return None
        except Exception as exc:
            logger.debug("pyc watermark verification skipped: %s", exc)
    else:
        logger.debug("no binding hash in credential, skipping binding check (legacy credential)")

    return cred


def _load_credential_raw() -> DeviceCredential | None:
    """Internal: load credential without binding verification."""
    # Primary: try Keychain
    try:
        from service.keychain import load_from_keychain
        kc_data = load_from_keychain()
        if kc_data is not None:
            return DeviceCredential(
                simei=kc_data["simei"],
                token=kc_data["token"],
                binding_hash=kc_data.get("binding_hash", ""),
            )
    except Exception as exc:
        logger.debug("keychain load error: %s", exc)

    # Fallback: file-based storage
    if not _CREDENTIAL_FILE.is_file():
        logger.debug("no credential file found at %s", _CREDENTIAL_FILE)
        return None

    try:
        raw = json.loads(_CREDENTIAL_FILE.read_text(encoding="utf-8"))
        simei = str(raw.get("simei", "")).strip()
        token = str(raw.get("token", "")).strip()
        if not simei or not token:
            logger.warning("credential file incomplete, ignoring")
            return None
        logger.info("credential loaded from file simei=%s", simei)
        return DeviceCredential(
            simei=simei,
            token=token,
            binding_hash=str(raw.get("binding_hash", "")),
        )
    except Exception as exc:
        logger.warning("failed to load credential from file: %s", exc)
        return None


def _apply_pyc_watermark(binding_hash: str) -> None:
    """Apply device-specific .pyc watermark (non-blocking, best-effort).

    Called once during first activation after binding_hash is computed.
    After watermarking, the integrity manifest must be regenerated to
    reflect the updated file hashes.
    """
    try:
        from service.pyc_watermark import apply_watermark
        count = apply_watermark(binding_hash)
        if count > 0:
            # Regenerate integrity manifest to include watermarked file hashes.
            # The HMAC key is embedded in the frozen binary, so we read it from
            # the integrity module.
            _regenerate_manifest_after_watermark()
    except Exception as exc:
        logger.debug("pyc watermark application skipped: %s", exc)


def _regenerate_manifest_after_watermark() -> None:
    """Regenerate integrity manifest after watermarking changes file hashes.

    Reads the HMAC key from the frozen integrity module and rewrites the
    manifest JSON with updated SHA-256 hashes and a fresh HMAC signature.
    """
    import sys
    if not getattr(sys, "frozen", False):
        return

    try:
        from service.integrity import (
            generate_manifest, _MANIFEST_HMAC_KEY, _is_hmac_key_available,
        )
        from pathlib import Path
        import json

        product_root = str(Path(sys._MEIPASS).parent)
        hmac_key = _MANIFEST_HMAC_KEY if _is_hmac_key_available() else ""
        manifest = generate_manifest(product_root, hmac_key=hmac_key)

        out = Path(sys._MEIPASS) / "integrity_manifest.json"
        out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info("integrity manifest regenerated after watermark (%d files)", manifest.get("total_files", 0))
    except Exception as exc:
        logger.warning("failed to regenerate manifest after watermark: %s", exc)
