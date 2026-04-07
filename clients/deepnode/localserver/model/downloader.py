"""Model download and local cache management.

Supports downloading from both HuggingFace and ModelScope with automatic
source selection: both sources are probed concurrently; the fastest
reachable one wins. If the winner fails mid-download, fallback to the
other source automatically.
"""

from __future__ import annotations

import logging
import os
import time
import concurrent.futures
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------

class Source(str, Enum):
    """Supported model download sources."""
    HUGGINGFACE = "huggingface"
    MODELSCOPE = "modelscope"


# Default mirror endpoints (optimized for China mainland)
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"
DEFAULT_MS_ENDPOINT = "https://modelscope.cn"

# Download retry / probe config
MAX_RETRIES = 3
RETRY_BASE_DELAY = 10

# Source probe config — download a real file from the model repo to
# measure actual CDN throughput instead of relying on API latency.
_PROBE_TIMEOUT = 20                      # seconds for probe HTTP request
_PROBE_REAL_FILE = "config.json"         # small real file to download for throughput test
_PROBE_FALLBACK_CHUNK_BYTES = 64_000     # fallback: bytes to read for API-only reachability check

# Persistent source preference file name (stored alongside model cache)
_SOURCE_PREF_FILE = ".deeppool_source_pref"


# ---------------------------------------------------------------------------
# Required file patterns for cache completeness check
# ---------------------------------------------------------------------------

_REQUIRED_FILES = (
    "config.json",
    "tokenizer_config.json",
)

_TOKENIZER_IMPL_FILES = (
    "tokenizer.json",
    "tokenizer.model",
    "vocab.txt",
    "merges.txt",
    "tiktoken_tokenizer.json",
)


# ---------------------------------------------------------------------------
# Source configuration
# ---------------------------------------------------------------------------

@dataclass
class SourceConfig:
    """Configuration for a single download source."""
    source: Source
    repo_id: str        # may differ between HF and MS for the same model
    endpoint: str

    @property
    def label(self) -> str:
        return f"{self.source.value}({self.repo_id})"


def _build_source_configs(
    repo_id: str,
    ms_repo_id: str | None = None,
    hf_endpoint: str = DEFAULT_HF_ENDPOINT,
    ms_endpoint: str = DEFAULT_MS_ENDPOINT,
) -> list[SourceConfig]:
    """Build source config list from repo IDs.

    Both HuggingFace and ModelScope use org/model format. Often the repo_id
    is identical on both platforms; if not, caller can supply ms_repo_id.

    ModelScope is listed first as the preferred default source for China
    region users where it typically offers faster and more reliable downloads.
    """
    configs: list[SourceConfig] = []
    # ModelScope first — preferred default for China region
    effective_ms_repo = ms_repo_id if ms_repo_id is not None else repo_id
    if effective_ms_repo:
        configs.append(
            SourceConfig(Source.MODELSCOPE, effective_ms_repo, ms_endpoint),
        )
    # HuggingFace as fallback
    configs.append(
        SourceConfig(Source.HUGGINGFACE, repo_id, hf_endpoint),
    )
    return configs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_model(
    repo_id: str,
    local_dir: Path,
    *,
    ms_repo_id: str | None = None,
    hf_endpoint: str = DEFAULT_HF_ENDPOINT,
    ms_endpoint: str = DEFAULT_MS_ENDPOINT,
    max_retries: int = MAX_RETRIES,
) -> Path:
    """Download model from the fastest available source.

    Probes HuggingFace and ModelScope concurrently; the first source that
    responds successfully and with decent speed wins. If the winner fails
    mid-download, falls back to the other source.

    Args:
        repo_id: Model repository ID (HuggingFace format, e.g. "Qwen/Qwen2-7B").
        local_dir: Local storage directory.
        ms_repo_id: Optional ModelScope repo ID if different from repo_id.
        hf_endpoint: HuggingFace mirror endpoint.
        ms_endpoint: ModelScope endpoint.
        max_retries: Max retry count per source.

    Returns:
        Path to the downloaded model directory.
    """
    if not repo_id or not repo_id.strip():
        raise ValueError("repo_id is required")

    local_dir = Path(local_dir).expanduser().resolve()

    if _is_model_cached(local_dir):
        logger.info("model already cached at %s, skip download", local_dir)
        return local_dir

    local_dir.mkdir(parents=True, exist_ok=True)

    sources = _build_source_configs(repo_id, ms_repo_id, hf_endpoint, ms_endpoint)
    ranked = _rank_sources(sources, local_dir=local_dir)

    if not ranked:
        raise RuntimeError(
            f"all download sources unreachable for {repo_id}, "
            f"tried: {[s.label for s in sources]}"
        )

    # Try each source in ranked order (best first)
    last_exc: Exception | None = None
    for src_cfg in ranked:
        try:
            _download_from_source(src_cfg, local_dir, max_retries)
            # Persist the winning source for next time
            _save_source_preference(local_dir, src_cfg.source)
            return local_dir
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "source %s failed: %s, trying next source...",
                src_cfg.label, exc,
            )

    raise RuntimeError(
        f"model download failed from all sources: {last_exc}"
    ) from last_exc


# Keep old name as alias for backward compatibility
download_model_hf = download_model


def repair_model_cache(
    repo_id: str,
    local_dir: Path,
    *,
    ms_repo_id: str | None = None,
    hf_endpoint: str = DEFAULT_HF_ENDPOINT,
    ms_endpoint: str = DEFAULT_MS_ENDPOINT,
    max_retries: int = MAX_RETRIES,
) -> Path:
    """Repair corrupt or incomplete model cache directory.

    Cleans known bad files then re-downloads missing parts from the
    fastest available source.
    """
    local_dir = Path(local_dir).expanduser().resolve()
    logger.warning("repairing model cache: repo=%s dir=%s", repo_id, local_dir)

    cleaned = 0
    for fname in (*_REQUIRED_FILES, *_TOKENIZER_IMPL_FILES):
        fp = local_dir / fname
        if fp.exists() and fp.stat().st_size == 0:
            fp.unlink()
            cleaned += 1
            logger.info("removed empty file: %s", fp)

    for tmp_file in local_dir.glob("*.incomplete"):
        tmp_file.unlink(missing_ok=True)
        cleaned += 1

    logger.info("cleaned %d corrupt/temp files, re-downloading missing parts...", cleaned)

    local_dir.mkdir(parents=True, exist_ok=True)

    sources = _build_source_configs(repo_id, ms_repo_id, hf_endpoint, ms_endpoint)
    ranked = _rank_sources(sources, local_dir=local_dir)

    if not ranked:
        raise RuntimeError(f"all download sources unreachable for repair: {repo_id}")

    last_exc: Exception | None = None
    for src_cfg in ranked:
        try:
            _download_from_source(src_cfg, local_dir, max_retries)
            _save_source_preference(local_dir, src_cfg.source)
            return local_dir
        except Exception as exc:
            last_exc = exc
            logger.warning("repair via %s failed: %s", src_cfg.label, exc)

    raise RuntimeError(f"model repair failed from all sources: {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# Source probing & ranking
#
# Strategy (in priority order):
#   1. Persistent preference — if a source succeeded last time for this repo,
#      try it first (skip probe entirely). Stored in a tiny file next to the
#      model cache so it survives across runs.
#   2. Real-file throughput probe — download config.json from the actual model
#      repo on each source concurrently, measuring real CDN throughput instead
#      of API latency. This reflects the actual download path including CDN
#      edge, SSL, and regional routing.
#   3. API reachability fallback — if the real file probe fails (e.g. repo
#      doesn't exist on that source), fall back to a lightweight API ping
#      to at least confirm the source is reachable.
#   4. Original list order — when probed throughputs are within a 30% margin,
#      preserve original list order (ModelScope first for China region).
# ---------------------------------------------------------------------------

@dataclass
class _ProbeResult:
    """Result of probing a single source."""
    config: SourceConfig
    reachable: bool
    speed_bps: float       # bytes per second (0 if unreachable)
    real_file: bool = False # True if throughput was measured from a real file download
    error: str = ""


def _rank_sources(
    sources: list[SourceConfig],
    local_dir: Path | None = None,
) -> list[SourceConfig]:
    """Probe all sources concurrently and return them sorted by suitability.

    If a persistent source preference exists and that source is still
    reachable, it is promoted to first place regardless of speed.

    Unreachable sources are excluded from the result.
    """
    if len(sources) <= 1:
        return sources

    # Check persistent preference from last successful download
    preferred = _load_source_preference(local_dir) if local_dir else None
    if preferred:
        logger.info("found persistent source preference: %s", preferred)

    logger.info(
        "probing %d download sources: %s",
        len(sources), [s.label for s in sources],
    )

    results: list[_ProbeResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(sources)) as pool:
        future_map = {pool.submit(_probe_source, s): s for s in sources}
        for future in concurrent.futures.as_completed(future_map):
            results.append(future.result())

    # Log probe results
    for r in results:
        if r.reachable:
            speed_kb = r.speed_bps / 1024
            probe_type = "real-file" if r.real_file else "api-only"
            logger.info(
                "  %s: reachable (%s), throughput %.1f KB/s",
                r.config.label, probe_type, speed_kb,
            )
        else:
            logger.info("  %s: unreachable (%s)", r.config.label, r.error)

    reachable = [r for r in results if r.reachable]
    if not reachable:
        return []

    # Build index for original list order (used as tiebreaker)
    source_order = {id(s): i for i, s in enumerate(sources)}

    # Sort: real-file probes rank higher than api-only; within same tier
    # sort by speed but with a 30% similarity margin preserving original order.
    def _sort_key(r: _ProbeResult) -> tuple[int, int, int]:
        tier = 0 if r.real_file else 1
        # Quantize speed into buckets so similar speeds don't flip order.
        # Bucket size = 30% of the max speed in this tier.
        max_in_tier = max(
            (x.speed_bps for x in reachable if x.real_file == r.real_file),
            default=1,
        )
        bucket_size = max(max_in_tier * 0.3, 1)
        speed_bucket = -int(r.speed_bps / bucket_size)
        original_idx = source_order.get(id(r.config), 99)
        return (tier, speed_bucket, original_idx)

    reachable.sort(key=_sort_key)

    # Promote persistent preference if it is reachable
    if preferred:
        for i, r in enumerate(reachable):
            if r.config.source.value == preferred and i > 0:
                logger.info(
                    "promoting previously successful source %s from rank %d to first",
                    r.config.label, i + 1,
                )
                reachable.insert(0, reachable.pop(i))
                break

    winner = reachable[0]
    probe_type = "real-file" if winner.real_file else "api-only"
    logger.info(
        "selected source: %s (%s, %.1f KB/s)",
        winner.config.label, probe_type, winner.speed_bps / 1024,
    )

    return [r.config for r in reachable]


# ---------------------------------------------------------------------------
# Source preference persistence
# ---------------------------------------------------------------------------

def _save_source_preference(local_dir: Path, source: Source) -> None:
    """Persist the successful download source for future runs."""
    try:
        pref_file = local_dir / _SOURCE_PREF_FILE
        pref_file.write_text(source.value, encoding="utf-8")
        logger.debug("saved source preference: %s -> %s", source.value, pref_file)
    except Exception as exc:
        logger.debug("failed to save source preference (non-fatal): %s", exc)


def _load_source_preference(local_dir: Path) -> str | None:
    """Load previously successful source name, or None."""
    try:
        pref_file = local_dir / _SOURCE_PREF_FILE
        if pref_file.exists():
            value = pref_file.read_text(encoding="utf-8").strip()
            return value if value else None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Source probing implementations
# ---------------------------------------------------------------------------

def _probe_source(src: SourceConfig) -> _ProbeResult:
    """Probe a single source by downloading a real model file for throughput measurement.

    Falls back to API reachability check if the real file is not available.
    """
    try:
        # Primary: download a real file from the model repo
        result = _probe_real_file(src)
        if result.reachable:
            return result
        # Fallback: API-only reachability check
        logger.debug(
            "real-file probe failed for %s (%s), falling back to API check",
            src.label, result.error,
        )
        return _probe_api_reachability(src)
    except Exception as exc:
        return _ProbeResult(src, False, 0, error=str(exc))


def _probe_real_file(src: SourceConfig) -> _ProbeResult:
    """Download config.json from the model repo to measure real CDN throughput."""
    import httpx

    if src.source == Source.HUGGINGFACE:
        url = f"{src.endpoint}/{src.repo_id}/resolve/main/{_PROBE_REAL_FILE}"
    elif src.source == Source.MODELSCOPE:
        url = (
            f"{src.endpoint}/api/v1/models/{src.repo_id}"
            f"/repo/files?Revision=master&FilePath={_PROBE_REAL_FILE}"
        )
    else:
        return _ProbeResult(src, False, 0, error=f"unknown source: {src.source}")

    try:
        start = time.monotonic()
        with httpx.Client(timeout=_PROBE_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            nbytes = len(resp.content)
        elapsed = max(time.monotonic() - start, 0.001)
        speed = nbytes / elapsed
        return _ProbeResult(src, True, speed, real_file=True)
    except httpx.HTTPStatusError as e:
        return _ProbeResult(
            src, False, 0,
            error=f"HTTP {e.response.status_code} for {_PROBE_REAL_FILE}",
        )
    except Exception as exc:
        return _ProbeResult(src, False, 0, error=str(exc))


def _probe_api_reachability(src: SourceConfig) -> _ProbeResult:
    """Lightweight API-only reachability check (no throughput measurement)."""
    import httpx

    if src.source == Source.HUGGINGFACE:
        url = f"{src.endpoint}/api/models/{src.repo_id}/revision/main"
    elif src.source == Source.MODELSCOPE:
        url = f"{src.endpoint}/api/v1/models/{src.repo_id}"
    else:
        return _ProbeResult(src, False, 0, error=f"unknown source: {src.source}")

    try:
        start = time.monotonic()
        with httpx.Client(timeout=_PROBE_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            nbytes = min(len(resp.content), _PROBE_FALLBACK_CHUNK_BYTES)
        elapsed = max(time.monotonic() - start, 0.001)
        # Mark as api-only (real_file=False) so it ranks below real-file probes
        return _ProbeResult(src, True, nbytes / elapsed, real_file=False)
    except httpx.HTTPStatusError as e:
        return _ProbeResult(
            src, False, 0,
            error=f"HTTP {e.response.status_code} (model may not exist on this source)",
        )
    except Exception as exc:
        return _ProbeResult(src, False, 0, error=str(exc))


# ---------------------------------------------------------------------------
# Source-specific download implementations
# ---------------------------------------------------------------------------

def _download_from_source(
    src: SourceConfig,
    local_dir: Path,
    max_retries: int,
) -> None:
    """Dispatch download to the appropriate source-specific implementation."""
    logger.info("downloading from %s to %s", src.label, local_dir)

    if src.source == Source.HUGGINGFACE:
        _download_huggingface(src, local_dir, max_retries)
    elif src.source == Source.MODELSCOPE:
        _download_modelscope(src, local_dir, max_retries)
    else:
        raise ValueError(f"unsupported source: {src.source}")


def _download_huggingface(
    src: SourceConfig,
    local_dir: Path,
    max_retries: int,
) -> None:
    """Download model via huggingface_hub snapshot_download."""
    os.environ["HF_ENDPOINT"] = src.endpoint

    _log_hf_repo_info(src.repo_id, src.endpoint)
    _retry_download(
        label=src.label,
        download_fn=lambda: _hf_snapshot(src.repo_id, local_dir, src.endpoint),
        max_retries=max_retries,
    )


def _hf_snapshot(repo_id: str, local_dir: Path, endpoint: str) -> None:
    """Single attempt of huggingface_hub snapshot_download."""
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(local_dir),
        endpoint=endpoint,
    )


def _download_modelscope(
    src: SourceConfig,
    local_dir: Path,
    max_retries: int,
) -> None:
    """Download model via modelscope snapshot_download."""
    _retry_download(
        label=src.label,
        download_fn=lambda: _ms_snapshot(src.repo_id, local_dir),
        max_retries=max_retries,
    )


def _ms_snapshot(repo_id: str, local_dir: Path) -> None:
    """Single attempt of modelscope snapshot_download.

    Handles both API versions:
    - New (>=1.18): from modelscope import snapshot_download
    - Old: from modelscope.hub.snapshot_download import snapshot_download
    """
    try:
        from modelscope import snapshot_download
    except ImportError:
        from modelscope.hub.snapshot_download import snapshot_download

    snapshot_download(
        model_id=repo_id,
        local_dir=str(local_dir),
    )


# ---------------------------------------------------------------------------
# Common retry logic
# ---------------------------------------------------------------------------

def _retry_download(
    label: str,
    download_fn: Callable[[], None],
    max_retries: int,
) -> None:
    """Execute download_fn with retry and exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            download_fn()
            logger.info("download completed: %s", label)
            return
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "download attempt %d/%d failed (%s): %s, retrying in %ds...",
                    attempt, max_retries, label, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "download failed after %d attempts (%s): %s",
                    max_retries, label, exc,
                )

    raise RuntimeError(
        f"download failed after {max_retries} attempts ({label}): {last_exc}"
    ) from last_exc


# ---------------------------------------------------------------------------
# HuggingFace repo info logging
# ---------------------------------------------------------------------------

def _log_hf_repo_info(repo_id: str, hf_endpoint: str) -> None:
    """Pre-fetch and log the full file list + total size before HF download."""
    try:
        from huggingface_hub import HfApi
        api = HfApi(endpoint=hf_endpoint)
        siblings = api.model_info(repo_id, revision="main").siblings or []
        total_bytes = sum(s.size or 0 for s in siblings)
        total_gb = total_bytes / (1024 ** 3)
        logger.info(
            "repo manifest: %d files, total %.2f GB",
            len(siblings), total_gb,
        )
        for s in sorted(siblings, key=lambda x: x.size or 0, reverse=True):
            size_mb = (s.size or 0) / (1024 ** 2)
            if size_mb > 100:
                logger.info("  %s  %.0f MB", s.rfilename, size_mb)
    except Exception as exc:
        logger.debug("failed to pre-fetch HF repo info (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Cache completeness check
# ---------------------------------------------------------------------------

def _is_model_cached(model_dir: Path) -> bool:
    """Check if model directory has all required files (weights + tokenizer)."""
    if not model_dir.is_dir():
        return False

    # Must have at least one weight file
    weight_patterns = ("*.safetensors", "*.bin", "*.gguf")
    has_weights = False
    for pattern in weight_patterns:
        if any(f.stat().st_size > 0 for f in model_dir.glob(pattern)):
            has_weights = True
            break
    if not has_weights:
        return False

    # Must have all required config files
    for fname in _REQUIRED_FILES:
        fp = model_dir / fname
        if not fp.exists() or fp.stat().st_size == 0:
            logger.debug("model cache incomplete: missing %s in %s", fname, model_dir)
            return False

    # Must have at least one tokenizer implementation file
    has_tokenizer = any(
        (model_dir / f).exists() and (model_dir / f).stat().st_size > 0
        for f in _TOKENIZER_IMPL_FILES
    )
    if not has_tokenizer:
        logger.debug("model cache incomplete: no tokenizer impl file in %s", model_dir)
        return False

    return True
