"""Device-specific .pyc watermarking for cross-machine tamper detection.

Appends a device-unique watermark (derived from binding_hash) to each .pyc
file in mlx-packages/. This makes every device's .pyc files byte-different,
so a patched .pyc from machine A cannot be copied to machine B — the integrity
manifest hash won't match.

Architecture:
  First activation (after save_credential computes binding_hash):
    1. Derive a 32-byte watermark key from binding_hash via HKDF-like derivation
    2. For each .pyc file in mlx-packages/:
       - Compute HMAC-SHA256(watermark_key, file_content) → 32-byte tag
       - Append tag to the file (Python VM ignores trailing bytes in .pyc)
    3. Write a marker file (.watermark_applied) to avoid re-applying

  Every startup:
    - Integrity manifest verifies SHA-256 of watermarked .pyc files
    - If attacker copies .pyc from another device, the watermark tag differs
      → SHA-256 hash mismatch → integrity check fails → startup blocked

Design notes:
  - The watermark is appended AFTER the valid .pyc content. CPython's import
    machinery reads the .pyc header (magic + flags + timestamp/size + marshalled
    code) and stops. Trailing bytes are ignored, so the .pyc loads normally.
  - The watermark tag is a cryptographic HMAC, not just random bytes. This
    means an attacker who knows the scheme still cannot forge a valid tag
    without the binding_hash (which is hardware-tied).
  - The integrity manifest must be regenerated AFTER watermarking, so the
    manifest hashes match the watermarked files.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Marker file indicating watermark has been applied to this installation
_WATERMARK_MARKER = ".watermark_applied"

# Size of the appended HMAC tag (SHA-256 = 32 bytes)
_TAG_SIZE = 32

# File extensions to watermark
_WATERMARK_EXTENSIONS = frozenset({".pyc"})


def _derive_watermark_key(binding_hash: str) -> bytes:
    """Derive a 32-byte watermark key from the binding hash.

    Uses a simple HKDF-expand-like derivation: SHA-256(binding_hash + salt).
    The salt ensures the watermark key differs from the binding hash itself.
    """
    material = f"pyc-watermark:{binding_hash}".encode("utf-8")
    return hashlib.sha256(material).digest()


def _compute_tag(key: bytes, content: bytes) -> bytes:
    """Compute HMAC-SHA256 tag for file content."""
    return hmac.new(key, content, hashlib.sha256).digest()


def apply_watermark(binding_hash: str, product_root: Optional[str] = None) -> int:
    """Apply device-specific watermark to all .pyc files in mlx-packages/.

    This should be called once after the first credential save. It appends
    a 32-byte HMAC tag to each .pyc file, making them device-unique.

    Args:
        binding_hash: the device binding hash (hardware-tied)
        product_root: path to the product root directory. If None, auto-detect
                      from sys._MEIPASS (frozen mode) or skip (dev mode).

    Returns:
        Number of files watermarked, or 0 if skipped.
    """
    import sys

    if not binding_hash:
        logger.debug("watermark skipped: no binding_hash")
        return 0

    # Resolve product root
    if product_root is None:
        if not getattr(sys, "frozen", False):
            logger.debug("watermark skipped: not frozen mode")
            return 0
        product_root = str(Path(sys._MEIPASS).parent)

    root = Path(product_root)
    mlx_dir = root / "mlx-packages"
    if not mlx_dir.is_dir():
        logger.debug("watermark skipped: mlx-packages/ not found")
        return 0

    # Check if already applied
    marker = mlx_dir / _WATERMARK_MARKER
    if marker.is_file():
        logger.debug("watermark already applied (marker exists)")
        return 0

    t0 = time.monotonic()
    key = _derive_watermark_key(binding_hash)
    count = 0

    for fpath in sorted(mlx_dir.rglob("*")):
        if not fpath.is_file() or fpath.suffix not in _WATERMARK_EXTENSIONS:
            continue

        try:
            content = fpath.read_bytes()
            tag = _compute_tag(key, content)
            # Append tag to file
            with open(fpath, "ab") as f:
                f.write(tag)
            count += 1
        except Exception as exc:
            logger.warning("watermark failed for %s: %s", fpath.name, exc)

    # Write marker with metadata
    try:
        marker.write_text(
            f"applied_at={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            f"files={count}\n"
            f"key_prefix={binding_hash[:8]}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("failed to write watermark marker: %s", exc)

    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "pyc watermark applied: %d files tagged (%dms) key=%s...%s",
        count, duration_ms, binding_hash[:8], binding_hash[-8:],
    )
    return count


def verify_watermark(binding_hash: str, product_root: Optional[str] = None) -> bool:
    """Verify that .pyc watermarks match the current device.

    Checks a random sample of watermarked files to detect cross-device copying.
    Returns True if verification passed or was skipped.

    Args:
        binding_hash: the device binding hash
        product_root: path to the product root directory

    Returns:
        True if watermarks are valid (or not applicable), False if mismatch.
    """
    import sys

    if not binding_hash:
        return True

    if product_root is None:
        if not getattr(sys, "frozen", False):
            return True
        product_root = str(Path(sys._MEIPASS).parent)

    root = Path(product_root)
    mlx_dir = root / "mlx-packages"
    marker = mlx_dir / _WATERMARK_MARKER

    if not marker.is_file():
        # Watermark not yet applied (first run or legacy install)
        return True

    key = _derive_watermark_key(binding_hash)
    checked = 0
    mismatched = 0

    for fpath in sorted(mlx_dir.rglob("*")):
        if not fpath.is_file() or fpath.suffix not in _WATERMARK_EXTENSIONS:
            continue

        try:
            raw = fpath.read_bytes()
            if len(raw) < _TAG_SIZE + 16:
                # File too small to have a watermark (likely not tagged)
                continue

            # Split: original content | 32-byte tag
            content = raw[:-_TAG_SIZE]
            stored_tag = raw[-_TAG_SIZE:]
            expected_tag = _compute_tag(key, content)

            if not hmac.compare_digest(stored_tag, expected_tag):
                mismatched += 1
                if mismatched <= 3:
                    logger.warning("watermark mismatch: %s", fpath.name)
            checked += 1
        except Exception as exc:
            logger.debug("watermark verify error for %s: %s", fpath.name, exc)

    if mismatched > 0:
        logger.error(
            "watermark verification FAILED: %d/%d files mismatched — "
            "files may have been copied from another device",
            mismatched, checked,
        )
        return False

    if checked > 0:
        logger.info("watermark verification passed: %d files checked", checked)
    return True
