"""Runtime integrity verification for DeepNode standalone builds.

This module provides tamper detection by comparing SHA-256 hashes of critical
files against a manifest generated at build time. The manifest is embedded
inside the frozen binary (via PyInstaller), making it difficult to modify
without reverse-engineering the entire binary.

Architecture:
  Build time:
    1. Build script compiles .py → .pyc and deletes .py sources
    2. Build script generates integrity_manifest.json with SHA-256 hashes
       of all critical files (*.pyc, *.so, *.dylib in mlx-packages/)
    3. HMAC-SHA256 signature computed over manifest content using a secret
       key embedded in this frozen module
    4. integrity_manifest.json (with HMAC) is placed in _internal/

  Runtime (this module):
    1. Load manifest from _internal/integrity_manifest.json
    2. Verify HMAC signature — reject if manifest was tampered
    3. Recompute SHA-256 for each file listed in the manifest
    4. Compare hashes — any mismatch indicates tampering
    5. Report results (caller decides whether to block startup)

Security layers:
  - HMAC signature prevents an attacker from modifying the manifest after
    build. The secret key is embedded in the frozen binary, requiring binary
    reverse-engineering to extract.
  - With Developer ID signing, the binary signature additionally protects
    both the embedded key and the manifest.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Manifest file name (placed in _internal/ by build script)
_MANIFEST_FILENAME = "integrity_manifest.json"

# File extensions to verify (includes .py for transformers sources kept uncompiled)
_CRITICAL_EXTENSIONS = frozenset({".pyc", ".so", ".dylib", ".py"})

# HMAC signing key — injected at build time by build_standalone_mac.sh.
# The placeholder below is replaced with a random 64-char hex string during
# each build. In development mode the placeholder is kept as-is, and HMAC
# verification is skipped gracefully.
_MANIFEST_HMAC_KEY = "__DEEPNODE_MANIFEST_HMAC_KEY_PLACEHOLDER__"


@dataclass
class IntegrityResult:
    """Result of an integrity verification check."""
    passed: bool
    total_files: int
    verified_files: int
    mismatched_files: list[str]
    missing_files: list[str]
    extra_files: list[str]
    duration_ms: int
    manifest_version: str
    build_timestamp: str


def _sha256_file(filepath: str, buf_size: int = 65536) -> str:
    """Compute SHA-256 hex digest for a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            data = f.read(buf_size)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def _find_manifest() -> Optional[Path]:
    """Locate the integrity manifest file.

    In frozen mode, the manifest is inside _internal/ (sys._MEIPASS).
    In onefile (--binary-only) mode, no manifest exists — verification is skipped
    because all code is embedded in the signed binary itself.
    In development mode, skip verification (no manifest expected).
    """
    if not getattr(sys, "frozen", False):
        return None

    base = Path(sys._MEIPASS)
    manifest_path = base / _MANIFEST_FILENAME
    if manifest_path.is_file():
        return manifest_path

    logger.warning("integrity manifest not found at %s", manifest_path)
    return None


def _load_manifest(manifest_path: Path) -> Optional[dict]:
    """Load, verify HMAC signature, and parse the integrity manifest JSON.

    The manifest contains an 'hmac' field added at build time. Verification
    recomputes HMAC-SHA256 over the canonical JSON (excluding the hmac field)
    using the key embedded in this module.
    """
    try:
        raw_bytes = manifest_path.read_bytes()
        data = json.loads(raw_bytes)
        if not isinstance(data, dict) or "files" not in data:
            logger.error("integrity manifest has invalid structure")
            return None

        # Verify HMAC if key is available (i.e. in frozen builds)
        stored_hmac = data.pop("hmac", None)
        if _is_hmac_key_available():
            if not stored_hmac:
                logger.error("integrity manifest missing HMAC signature")
                return None
            # Recompute HMAC over canonical JSON (without the hmac field)
            canonical = json.dumps(data, sort_keys=True, ensure_ascii=True).encode("utf-8")
            expected = hmac.new(
                _MANIFEST_HMAC_KEY.encode("utf-8"), canonical, hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, stored_hmac):
                logger.error("integrity manifest HMAC mismatch — manifest may be tampered")
                return None
            logger.debug("integrity manifest HMAC verified")
        else:
            logger.debug("HMAC verification skipped (dev mode or placeholder key)")

        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("failed to load integrity manifest: %s", exc)
        return None


def _is_hmac_key_available() -> bool:
    """Check if the HMAC key has been injected (not the placeholder)."""
    return (
        _MANIFEST_HMAC_KEY
        and "PLACEHOLDER" not in _MANIFEST_HMAC_KEY
        and len(_MANIFEST_HMAC_KEY) >= 32
    )


def verify_integrity() -> Optional[IntegrityResult]:
    """Verify file integrity against the build-time manifest.

    Returns:
        IntegrityResult if verification was performed, None if skipped
        (e.g. development mode or missing manifest).
    """
    manifest_path = _find_manifest()
    if manifest_path is None:
        logger.debug("integrity verification skipped (no manifest)")
        return None

    manifest = _load_manifest(manifest_path)
    if manifest is None:
        return IntegrityResult(
            passed=False, total_files=0, verified_files=0,
            mismatched_files=[], missing_files=[], extra_files=[],
            duration_ms=0, manifest_version="", build_timestamp="",
        )

    t0 = time.monotonic()

    # Resolve base directory (product root, one level above _internal/)
    product_root = Path(sys._MEIPASS).parent

    file_entries: dict[str, str] = manifest.get("files", {})
    version = manifest.get("version", "unknown")
    build_ts = manifest.get("build_timestamp", "unknown")
    total = len(file_entries)

    mismatched: list[str] = []
    missing: list[str] = []
    verified = 0

    for rel_path, expected_hash in file_entries.items():
        abs_path = product_root / rel_path
        if not abs_path.is_file():
            missing.append(rel_path)
            continue

        actual_hash = _sha256_file(str(abs_path))
        if actual_hash != expected_hash:
            mismatched.append(rel_path)
            logger.warning(
                "integrity mismatch: %s expected=%s actual=%s",
                rel_path, expected_hash[:16], actual_hash[:16],
            )
        else:
            verified += 1

    duration_ms = int((time.monotonic() - t0) * 1000)
    passed = len(mismatched) == 0 and len(missing) == 0

    result = IntegrityResult(
        passed=passed,
        total_files=total,
        verified_files=verified,
        mismatched_files=mismatched,
        missing_files=missing,
        extra_files=[],  # not checked yet
        duration_ms=duration_ms,
        manifest_version=version,
        build_timestamp=build_ts,
    )

    if passed:
        logger.info(
            "integrity verification passed: %d/%d files ok (%dms)",
            verified, total, duration_ms,
        )
    else:
        logger.error(
            "integrity verification FAILED: %d mismatched, %d missing out of %d (%dms)",
            len(mismatched), len(missing), total, duration_ms,
        )

    return result


def generate_manifest(product_root: str, version: str = "", hmac_key: str = "") -> dict:
    """Generate an integrity manifest for a built product directory.

    This is called by the build script (not at runtime).

    Args:
        product_root: path to the built product directory (e.g. dist/deepnode-server/)
        version: build version string
        hmac_key: if provided, compute and embed HMAC-SHA256 signature

    Returns:
        Manifest dict with file hashes (and optional HMAC).
    """
    root = Path(product_root)
    files: dict[str, str] = {}

    # Hash files in mlx-packages/ (the primary attack surface)
    mlx_dir = root / "mlx-packages"
    if mlx_dir.is_dir():
        for fpath in sorted(mlx_dir.rglob("*")):
            if fpath.is_file() and fpath.suffix in _CRITICAL_EXTENSIONS:
                rel = str(fpath.relative_to(root))
                files[rel] = _sha256_file(str(fpath))

    # Hash files in _internal/ (frozen runtime dependencies)
    internal_dir = root / "_internal"
    if internal_dir.is_dir():
        for fpath in sorted(internal_dir.rglob("*")):
            if fpath.is_file() and fpath.suffix in (".so", ".dylib"):
                rel = str(fpath.relative_to(root))
                files[rel] = _sha256_file(str(fpath))

    # Hash the main binary
    for bin_name in ("deepnode-server-bin",):
        bin_path = root / bin_name
        if bin_path.is_file():
            files[bin_name] = _sha256_file(str(bin_path))

    manifest = {
        "version": version,
        "build_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_files": len(files),
        "files": files,
    }

    # Sign manifest with HMAC-SHA256 if key is provided
    if hmac_key:
        canonical = json.dumps(manifest, sort_keys=True, ensure_ascii=True).encode("utf-8")
        manifest["hmac"] = hmac.new(
            hmac_key.encode("utf-8"), canonical, hashlib.sha256,
        ).hexdigest()
        logger.info("integrity manifest HMAC signature computed")

    logger.info(
        "integrity manifest generated: %d files, version=%s, hmac=%s",
        len(files), version, bool(hmac_key),
    )
    return manifest
