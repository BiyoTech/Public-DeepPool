"""gRPC communication module — inference server and platform client."""

from .infer_server import start_grpc_server
from .platform_client import (
    ModelDeployConfig,
    PlatformClient,
    close_shared_platform_client,
    get_shared_platform_client,
)

__all__ = [
    "start_grpc_server",
    "ModelDeployConfig",
    "PlatformClient",
    "close_shared_platform_client",
    "get_shared_platform_client",
]
