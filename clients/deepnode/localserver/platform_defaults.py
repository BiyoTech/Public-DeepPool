"""Platform gRPC connection defaults — baked into the binary at build time.

This module provides the canonical platform gRPC targets and TLS settings
for each build profile (dev / prod).  The active profile is determined by
the environment variable DEEPPOOL_PROFILE (set by the build script), with
a fallback to "dev" for local development.

Design rationale:
  - Platform gRPC addresses are infrastructure constants, not user settings.
  - Embedding them in code prevents end-users from seeing or tampering with
    server IPs in the shipped config.yaml.
  - TLS is always enabled for prod and always disabled for dev.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Build profile is injected by the build script via DEEPPOOL_PROFILE env var.
# At runtime this env var is baked into the PyInstaller binary (see runtime hook).
_PROFILE = os.environ.get("DEEPPOOL_PROFILE", "dev").strip().lower()


@dataclass(frozen=True)
class PlatformDefaults:
    """Immutable platform connection defaults for a given build profile."""
    manager_grpc_target: str
    scheduler_grpc_target: str
    nodemanager_grpc_target: str
    grpc_tls: bool
    grpc_tls_ca_cert: str  # PEM path; empty = use system root certificates


# ── Profile definitions ──

_DEV = PlatformDefaults(
    manager_grpc_target="101.33.255.185:9090",
    scheduler_grpc_target="101.33.255.185:9091",
    nodemanager_grpc_target="101.33.255.185:9092",
    grpc_tls=False,
    grpc_tls_ca_cert="",
)

_PROD = PlatformDefaults(
    manager_grpc_target="deeppool.tech:9090",
    scheduler_grpc_target="deeppool.tech:9091",
    nodemanager_grpc_target="deeppool.tech:9092",
    grpc_tls=True,
    grpc_tls_ca_cert="",
)

_PROFILES: dict[str, PlatformDefaults] = {
    "dev": _DEV,
    "prod": _PROD,
}


def get_platform_defaults() -> PlatformDefaults:
    """Return the platform defaults for the active build profile."""
    defaults = _PROFILES.get(_PROFILE)
    if defaults is None:
        logger.warning("unknown DEEPPOOL_PROFILE=%s, falling back to dev", _PROFILE)
        defaults = _DEV
    logger.info(
        "platform defaults loaded: profile=%s manager=%s nodemanager=%s tls=%s",
        _PROFILE, defaults.manager_grpc_target,
        defaults.nodemanager_grpc_target, defaults.grpc_tls,
    )
    return defaults


def get_profile() -> str:
    """Return the active build profile name."""
    return _PROFILE
