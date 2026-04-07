"""platform manager gRPC 客户端封装。

后台服务间通信统一走 gRPC。本模块封装了 client node 与 platform manager 之间的
所有 gRPC 调用，包括获取模型部署配置和设备注册。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import grpc

from generated import manager_service_pb2, manager_service_pb2_grpc

logger = logging.getLogger(__name__)


def _create_grpc_channel(target: str, use_tls: bool, ca_cert: str = "") -> grpc.Channel:
    """根据 TLS 配置创建 gRPC channel。

    Args:
        target: gRPC 地址
        use_tls: 是否启用 TLS
        ca_cert: CA 证书路径（PEM），留空使用系统根证书

    Returns:
        grpc.Channel 实例
    """
    if not use_tls:
        return grpc.insecure_channel(target)

    # 加载 CA 证书（留空则传 None，grpc 将使用系统根证书）
    root_certs = None
    if ca_cert:
        with open(ca_cert, "rb") as f:
            root_certs = f.read()
        logger.info("gRPC TLS: using custom CA cert=%s", ca_cert)
    else:
        logger.info("gRPC TLS: using system root certificates")

    credentials = grpc.ssl_channel_credentials(root_certificates=root_certs)
    return grpc.secure_channel(target, credentials)


@dataclass
class ModelDeployConfig:
    """模型部署配置，由 platform manager 下发。"""
    model_name: str         # 模型短名称，如 "Qwen2-7B-Instruct"
    repo_id: str            # HuggingFace 仓库 ID，如 "Qwen/Qwen2-7B-Instruct"
    model_base_dir: str     # 模型本地存储根目录，如 "~/.deeppool/models"
    rpc_host: str
    rpc_port: int
    engine: str             # 推理引擎标识，留空则由客户端自动检测
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceInfo:
    """设备信息。"""
    device_id: int
    user_id: int
    simei: str
    device_ip: str
    device_config: str
    created_at: str
    updated_at: str


class PlatformClient:
    """与 platform manager 通信的 gRPC 客户端。

    Args:
        grpc_target: manager gRPC 地址，如 "127.0.0.1:9090"
        auth_token: 用户鉴权 token（不带 Bearer 前缀）
        timeout: 单次 RPC 超时秒数
        use_tls: 是否使用 TLS 加密连接
        ca_cert: CA 证书文件路径（PEM），留空则使用系统根证书
    """

    def __init__(
        self,
        grpc_target: str,
        auth_token: str,
        timeout: int = 20,
        use_tls: bool = False,
        ca_cert: str = "",
    ):
        self._target = grpc_target
        self._token = auth_token.strip()
        self._timeout = timeout
        self._channel = _create_grpc_channel(grpc_target, use_tls, ca_cert)
        self._stub = manager_service_pb2_grpc.ManagerServiceStub(self._channel)
        logger.info("platform grpc client created target=%s tls=%s", self._target, use_tls)

    def get_model_deploy_config(
        self, simei: str, supported_models: list[str]
    ) -> ModelDeployConfig:
        """获取单个模型部署配置。"""
        req = manager_service_pb2.GetModelDeployConfigRequest(
            simei=simei,
            supported_models=supported_models,
            auth_token=self._token,
        )
        try:
            resp = self._stub.GetModelDeployConfig(req, timeout=self._timeout)
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc GetModelDeployConfig failed: %s", detail)
            raise RuntimeError(f"GetModelDeployConfig failed: {detail}") from exc

        cfg = resp.config
        options = dict(cfg.options)
        logger.info(
            "got deploy config model=%s repo=%s engine=%s rpc=%s:%d",
            cfg.model_name, cfg.repo_id, cfg.engine, cfg.rpc_host, cfg.rpc_port,
        )
        return ModelDeployConfig(
            model_name=cfg.model_name,
            repo_id=cfg.repo_id,
            model_base_dir=options.pop("model_base_dir", "~/.deeppool/models"),
            rpc_host=cfg.rpc_host,
            rpc_port=cfg.rpc_port,
            engine=cfg.engine,
            options=options,
        )

    def get_multi_model_deploy_configs(
        self, simei: str, supported_models: list[str]
    ) -> list[ModelDeployConfig]:
        """获取多模型部署配置列表。

        尝试调用平台的 GetMultiModelDeployConfigs RPC；若平台尚未支持该接口，
        则 fallback 到单模型接口 get_model_deploy_config，返回单元素列表。

        Args:
            simei: 设备唯一标识
            supported_models: 客户端支持的模型列表

        Returns:
            模型部署配置列表，可能为空（平台未分配任何模型时）。
        """
        # 优先尝试批量接口
        try:
            req = manager_service_pb2.GetMultiModelDeployConfigsRequest(
                simei=simei,
                supported_models=supported_models,
                auth_token=self._token,
            )
            resp = self._stub.GetMultiModelDeployConfigs(req, timeout=self._timeout)
            configs = []
            for cfg in resp.configs:
                options = dict(cfg.options)
                configs.append(ModelDeployConfig(
                    model_name=cfg.model_name,
                    repo_id=cfg.repo_id,
                    model_base_dir=options.pop("model_base_dir", "~/.deeppool/models"),
                    rpc_host=cfg.rpc_host,
                    rpc_port=cfg.rpc_port,
                    engine=cfg.engine,
                    options=options,
                ))
            logger.info("got %d multi-model deploy configs from platform", len(configs))
            return configs
        except (grpc.RpcError, AttributeError) as exc:
            # 平台尚未实现批量接口，fallback 到单模型接口
            logger.info(
                "GetMultiModelDeployConfigs not available (%s), falling back to single-model API",
                type(exc).__name__,
            )

        # Fallback: 单模型接口
        try:
            single = self.get_model_deploy_config(simei=simei, supported_models=supported_models)
            if single.model_name:
                return [single]
            return []
        except RuntimeError:
            logger.warning("fallback single-model deploy config also failed")
            return []

    def register_device(
        self, simei: str, device_ip: str, device_config: str,
        registered_models: list[str] | None = None,
    ) -> DeviceInfo:
        """注册设备信息到平台。

        Args:
            simei: 设备唯一标识
            device_ip: 设备 IP
            device_config: 设备配置 JSON 字符串
            registered_models: 设备已注册的模型列表（独立字段）
        """
        req = manager_service_pb2.RegisterDeviceRequest(
            simei=simei,
            device_ip=device_ip,
            device_config=device_config,
            auth_token=self._token,
            registered_models=registered_models or [],
        )
        try:
            resp = self._stub.RegisterDevice(req, timeout=self._timeout)
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.warning("grpc RegisterDevice failed: %s", detail)
            raise RuntimeError(f"RegisterDevice failed: {detail}") from exc

        d = resp.device
        logger.info("device registered simei=%s device_id=%d", d.simei, d.device_id)
        return DeviceInfo(
            device_id=d.device_id,
            user_id=d.user_id,
            simei=d.simei,
            device_ip=d.device_ip,
            device_config=d.device_config,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )

    def report_infer_logs(
        self, simei: str, logs: list[dict]
    ) -> int:
        """批量上报本地推理日志到平台。

        Args:
            simei: 设备 SIMEI
            logs: 日志条目列表，每条包含 request_id, model_name, prompt_tokens,
                  completion_tokens, total_tokens, reasoning_tokens, duration_ms,
                  stream, success, error_message, created_at_ms 等字段

        Returns:
            平台实际接受的条数
        """
        entries = []
        for log_entry in logs:
            entries.append(manager_service_pb2.ClientInferLogEntry(
                request_id=log_entry.get("request_id", ""),
                simei=simei,
                model_name=log_entry.get("model_name", ""),
                prompt_tokens=log_entry.get("prompt_tokens", 0),
                completion_tokens=log_entry.get("completion_tokens", 0),
                total_tokens=log_entry.get("total_tokens", 0),
                reasoning_tokens=log_entry.get("reasoning_tokens", 0),
                duration_ms=log_entry.get("duration_ms", 0),
                stream=log_entry.get("stream", False),
                success=log_entry.get("success", True),
                error_message=log_entry.get("error_message", ""),
                created_at_ms=log_entry.get("created_at_ms", 0),
                # Function Call 指标
                tool_call_count=log_entry.get("tool_call_count", 0),
                tool_call_success=log_entry.get("tool_call_success", True),
                tool_call_retried=log_entry.get("tool_call_retried", False),
                tool_call_parse_ms=log_entry.get("tool_call_parse_ms", 0),
            ))

        req = manager_service_pb2.ReportInferLogsRequest(
            auth_token=self._token,
            simei=simei,
            logs=entries,
        )
        try:
            resp = self._stub.ReportInferLogs(req, timeout=self._timeout)
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc ReportInferLogs failed: %s", detail)
            raise RuntimeError(f"ReportInferLogs failed: {detail}") from exc

        logger.info("reported %d/%d infer logs simei=%s", resp.accepted, len(logs), simei)
        return resp.accepted

    def update_device_status(self, simei: str, status: str) -> bool:
        """更新设备合法性状态到平台。

        Args:
            simei: 设备 SIMEI
            status: 合法性状态，"active" / "blocked" / "cheating"

        Returns:
            是否更新成功
        """
        req = manager_service_pb2.UpdateDeviceStatusRequest(
            auth_token=self._token,
            simei=simei,
            status=status,
        )
        try:
            resp = self._stub.UpdateDeviceStatus(req, timeout=self._timeout)
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc UpdateDeviceStatus failed: %s", detail)
            return False

        logger.info("device status updated simei=%s status=%s ok=%s", simei, status, resp.ok)
        return resp.ok

    def update_device(
        self, simei: str, device_config: str, device_ip: str = "",
    ) -> DeviceInfo:
        """更新设备信息到平台（模型加载完成后更新 device_config）。

        Args:
            simei: 设备 SIMEI
            device_config: 设备配置 JSON 字符串
            device_ip: 设备 IP（可选，留空则不更新）
        """
        req = manager_service_pb2.UpdateDeviceRequest(
            simei=simei,
            device_ip=device_ip,
            device_config=device_config,
            auth_token=self._token,
        )
        try:
            resp = self._stub.UpdateDevice(req, timeout=self._timeout)
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc UpdateDevice failed: %s", detail)
            raise RuntimeError(f"UpdateDevice failed: {detail}") from exc

        d = resp.device
        logger.info("device updated simei=%s device_id=%d", d.simei, d.device_id)
        return DeviceInfo(
            device_id=d.device_id,
            user_id=d.user_id,
            simei=d.simei,
            device_ip=d.device_ip,
            device_config=d.device_config,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )

    def login(self, account: str, password: str) -> dict:
        """用户登录（无需 auth_token）。

        Returns:
            {"token": str, "user": {...}} 字典
        """
        req = manager_service_pb2.LoginRequest(
            account=account,
            password=password,
        )
        try:
            resp = self._stub.Login(req, timeout=self._timeout)
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc Login failed: %s", detail)
            raise RuntimeError(f"Login failed: {detail}") from exc

        user = resp.user
        logger.info("grpc Login success uid=%d username=%s", user.id, user.username)
        return {
            "token": resp.token,
            "user": {
                "id": user.id,
                "username": user.username,
                "phone": user.phone,
                "email": user.email,
                "role": user.role,
                "identity": user.identity,
                "user_type": user.user_type,
            },
        }

    def register_user(
        self, username: str, password: str, phone: str, email: str,
        identity: str = "", user_type: str = "",
    ) -> dict:
        """用户注册（无需 auth_token）。

        Returns:
            {"id": int, "username": str, ...} 用户信息字典
        """
        req = manager_service_pb2.RegisterUserRequest(
            username=username,
            password=password,
            phone=phone,
            email=email,
            identity=identity,
            user_type=user_type,
        )
        try:
            resp = self._stub.RegisterUser(req, timeout=self._timeout)
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc RegisterUser failed: %s", detail)
            raise RuntimeError(f"RegisterUser failed: {detail}") from exc

        user = resp.user
        logger.info("grpc RegisterUser success uid=%d username=%s", user.id, user.username)
        return {
            "id": user.id,
            "username": user.username,
            "phone": user.phone,
            "email": user.email,
            "role": user.role,
            "identity": user.identity,
            "user_type": user.user_type,
        }

    def get_device(self, simei: str) -> DeviceInfo | None:
        """Query device info.

        Returns:
            DeviceInfo or None (device not found).
        """
        token_prefix = self._token[:8] + "..." if len(self._token) > 8 else self._token
        logger.debug("grpc GetDevice simei=%s token_prefix=%s", simei, token_prefix)
        req = manager_service_pb2.GetDeviceRequest(
            simei=simei,
            auth_token=self._token,
        )
        try:
            resp = self._stub.GetDevice(req, timeout=self._timeout)
        except grpc.RpcError as exc:
            code = exc.code() if hasattr(exc, "code") else None
            if code == grpc.StatusCode.NOT_FOUND:
                return None
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc GetDevice failed: %s", detail)
            raise RuntimeError(f"GetDevice failed: {detail}") from exc

        d = resp.device
        logger.info("grpc GetDevice simei=%s device_id=%d", d.simei, d.device_id)
        return DeviceInfo(
            device_id=d.device_id,
            user_id=d.user_id,
            simei=d.simei,
            device_ip=d.device_ip,
            device_config=d.device_config,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )

    def close(self):
        """关闭 gRPC channel。"""
        self._channel.close()
        logger.info("platform grpc channel closed")
