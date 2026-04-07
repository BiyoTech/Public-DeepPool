"""gRPC 通信模块 — 推理服务端与平台客户端。"""

from .infer_server import start_grpc_server
from .platform_client import ModelDeployConfig, PlatformClient

__all__ = ["start_grpc_server", "ModelDeployConfig", "PlatformClient"]
