"""Platform manager gRPC client with connection pooling and automatic retry.

All client-node ↔ platform-manager communication goes through gRPC.
This module provides:
  - PlatformClient: low-level gRPC client wrapping every Manager RPC
  - get_shared_platform_client(): module-level singleton factory that reuses
    the underlying gRPC channel across requests, with automatic reconnect
    on transient failures
  - _retry_on_transient(): retry decorator for idempotent / read-only RPCs
  - Token-expired detection: when an RPC receives UNAUTHENTICATED or a detail
    containing "expired token", the caller can invoke TokenManager.refresh_token()
    and retry once automatically.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

import grpc

from generated import manager_service_pb2, manager_service_pb2_grpc

logger = logging.getLogger(__name__)

T = TypeVar("T")

# gRPC status codes considered transient (safe to retry for idempotent calls)
_RETRYABLE_CODES = frozenset({
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
})

# gRPC status codes indicating token expiry / auth failure
_AUTH_FAILURE_CODES = frozenset({
    grpc.StatusCode.UNAUTHENTICATED,
    grpc.StatusCode.PERMISSION_DENIED,
})

# Substrings in gRPC error details that signal token expiry
_TOKEN_EXPIRED_HINTS = ("expired token", "invalid or expired token", "token expired")

# Default retry parameters
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BASE_DELAY = 1.0  # seconds


def _is_token_expired_error(exc: grpc.RpcError) -> bool:
    """Determine whether a gRPC error indicates an expired/invalid auth token."""
    code = exc.code() if hasattr(exc, "code") else None
    if code in _AUTH_FAILURE_CODES:
        return True
    detail = (exc.details() if hasattr(exc, "details") else str(exc)).lower()
    return any(hint in detail for hint in _TOKEN_EXPIRED_HINTS)


def _retry_on_transient(
    fn: Callable[..., T],
    *args: Any,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_BASE_DELAY,
    **kwargs: Any,
) -> T:
    """Execute *fn* with exponential-backoff retry on transient gRPC errors.

    Only retries when the gRPC status code is in _RETRYABLE_CODES.
    Non-retryable errors are raised immediately.

    Args:
        fn:          callable to invoke
        max_retries: total attempts (including the first one)
        base_delay:  initial backoff delay in seconds (doubles each attempt)
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except grpc.RpcError as exc:
            code = exc.code() if hasattr(exc, "code") else None
            if code not in _RETRYABLE_CODES or attempt >= max_retries:
                raise
            last_exc = exc
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "transient gRPC error (code=%s, attempt=%d/%d), retrying in %.1fs: %s",
                code, attempt, max_retries, delay,
                exc.details() if hasattr(exc, "details") else str(exc),
            )
            time.sleep(delay)
    # Should not reach here, but satisfy type checker
    raise last_exc  # type: ignore[misc]


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
    """Device info returned from platform after registration/query."""
    device_id: int
    user_id: int
    simei: str
    device_ip: str
    device_config: str
    created_at: str
    updated_at: str
    status: str = "active"  # "active" / "blocked" / "cheating"


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

    def _call_with_token_refresh(
        self,
        rpc_fn: Callable[..., T],
        build_request: Callable[[str], Any],
        rpc_name: str,
        *,
        use_retry: bool = True,
    ) -> T:
        """Execute an RPC with automatic token-refresh-and-retry on auth failure.

        Flow:
          1. Build request using current token → invoke RPC (with transient retry)
          2. If RPC raises a token-expired error:
             a. Ask TokenManager to refresh the token
             b. Rebuild request with new token → retry once
          3. If refresh fails or is unavailable, raise the original error.

        Args:
            rpc_fn:        The gRPC stub method to call.
            build_request: A callable that receives the current token and returns
                           the protobuf request message.
            rpc_name:      Human-readable RPC name for logging.
            use_retry:     Whether to wrap the RPC call with _retry_on_transient.
        """
        req = build_request(self._token)
        try:
            if use_retry:
                return _retry_on_transient(rpc_fn, req, timeout=self._timeout)
            return rpc_fn(req, timeout=self._timeout)
        except grpc.RpcError as exc:
            if not _is_token_expired_error(exc):
                raise

            # Attempt token refresh
            logger.warning(
                "%s: token expired, attempting refresh", rpc_name,
            )
            from service.token_manager import get_token_manager, TokenExpiredError
            tm = get_token_manager()
            if tm is None:
                raise
            try:
                new_token = tm.refresh_token()
            except TokenExpiredError:
                raise exc  # re-raise the original gRPC error

            # Update our own token and retry once
            self._token = new_token
            req = build_request(new_token)
            logger.info("%s: retrying with refreshed token", rpc_name)
            if use_retry:
                return _retry_on_transient(rpc_fn, req, timeout=self._timeout)
            return rpc_fn(req, timeout=self._timeout)

    def get_model_deploy_config(
        self, simei: str, supported_models: list[str]
    ) -> ModelDeployConfig:
        """Get single model deploy config (idempotent, retries on transient errors)."""
        def _build(token: str):
            return manager_service_pb2.GetModelDeployConfigRequest(
                simei=simei, supported_models=supported_models, auth_token=token,
            )

        try:
            resp = self._call_with_token_refresh(
                self._stub.GetModelDeployConfig, _build, "GetModelDeployConfig",
            )
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
        """Get multi-model deploy config list from platform.

        Tries batch API first; falls back to single-model API if unavailable.

        Args:
            simei: device SIMEI
            supported_models: models the client can run

        Returns:
            List of deploy configs (may be empty if platform assigned nothing).
        """
        def _build(token: str):
            return manager_service_pb2.GetMultiModelDeployConfigsRequest(
                simei=simei, supported_models=supported_models, auth_token=token,
            )

        # Prefer batch API (idempotent, retries on transient errors)
        try:
            resp = self._call_with_token_refresh(
                self._stub.GetMultiModelDeployConfigs, _build,
                "GetMultiModelDeployConfigs",
            )
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
            # Platform hasn't implemented the batch API yet — fall back
            logger.info(
                "GetMultiModelDeployConfigs not available (%s), falling back to single-model API",
                type(exc).__name__,
            )

        # Fallback: single-model API
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
        """Register device info on platform.

        Args:
            simei: device SIMEI
            device_ip: device IP
            device_config: device config JSON string
            registered_models: models already loaded on device
        """
        def _build(token: str):
            return manager_service_pb2.RegisterDeviceRequest(
                simei=simei, device_ip=device_ip, device_config=device_config,
                auth_token=token, registered_models=registered_models or [],
            )

        try:
            resp = self._call_with_token_refresh(
                self._stub.RegisterDevice, _build, "RegisterDevice",
                use_retry=False,
            )
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.warning("grpc RegisterDevice failed: %s", detail)
            raise RuntimeError(f"RegisterDevice failed: {detail}") from exc

        d = resp.device
        logger.info("device registered simei=%s device_id=%d status=%s", d.simei, d.device_id, d.status)
        return DeviceInfo(
            device_id=d.device_id,
            user_id=d.user_id,
            simei=d.simei,
            device_ip=d.device_ip,
            device_config=d.device_config,
            created_at=d.created_at,
            updated_at=d.updated_at,
            status=d.status or "active",
        )

    def report_infer_logs(
        self, simei: str, logs: list[dict]
    ) -> int:
        """Batch-report local inference logs to platform.

        Args:
            simei: device SIMEI
            logs: log entry dicts

        Returns:
            Number of entries accepted by platform.
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
                tool_call_count=log_entry.get("tool_call_count", 0),
                tool_call_success=log_entry.get("tool_call_success", True),
                tool_call_retried=log_entry.get("tool_call_retried", False),
                tool_call_parse_ms=log_entry.get("tool_call_parse_ms", 0),
            ))

        def _build(token: str):
            return manager_service_pb2.ReportInferLogsRequest(
                auth_token=token, simei=simei, logs=entries,
            )

        try:
            resp = self._call_with_token_refresh(
                self._stub.ReportInferLogs, _build, "ReportInferLogs",
            )
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc ReportInferLogs failed: %s", detail)
            raise RuntimeError(f"ReportInferLogs failed: {detail}") from exc

        logger.info("reported %d/%d infer logs simei=%s", resp.accepted, len(logs), simei)
        return resp.accepted

    def update_device_status(self, simei: str, status: str) -> bool:
        """Update device validity status on platform.

        Args:
            simei: device SIMEI
            status: "active" / "blocked" / "cheating"

        Returns:
            Whether the update succeeded.
        """
        def _build(token: str):
            return manager_service_pb2.UpdateDeviceStatusRequest(
                auth_token=token, simei=simei, status=status,
            )

        try:
            resp = self._call_with_token_refresh(
                self._stub.UpdateDeviceStatus, _build, "UpdateDeviceStatus",
                use_retry=False,
            )
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc UpdateDeviceStatus failed: %s", detail)
            return False

        logger.info("device status updated simei=%s status=%s ok=%s", simei, status, resp.ok)
        return resp.ok

    def update_device(
        self, simei: str, device_config: str, device_ip: str = "",
        registered_models: list[str] | None = None,
    ) -> DeviceInfo:
        """Update device info on platform.

        Args:
            simei: device SIMEI
            device_config: device config JSON string
            device_ip: device IP (optional, empty = no change)
            registered_models: models actually loaded and serving (optional)
        """
        def _build(token: str):
            return manager_service_pb2.UpdateDeviceRequest(
                simei=simei, device_ip=device_ip, device_config=device_config,
                auth_token=token, registered_models=registered_models or [],
            )

        try:
            resp = self._call_with_token_refresh(
                self._stub.UpdateDevice, _build, "UpdateDevice",
                use_retry=False,
            )
        except grpc.RpcError as exc:
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc UpdateDevice failed: %s", detail)
            raise RuntimeError(f"UpdateDevice failed: {detail}") from exc

        d = resp.device
        logger.info("device updated simei=%s device_id=%d status=%s", d.simei, d.device_id, d.status)
        return DeviceInfo(
            device_id=d.device_id,
            user_id=d.user_id,
            simei=d.simei,
            device_ip=d.device_ip,
            device_config=d.device_config,
            created_at=d.created_at,
            updated_at=d.updated_at,
            status=d.status or "active",
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

        def _build(token: str):
            return manager_service_pb2.GetDeviceRequest(
                simei=simei, auth_token=token,
            )

        try:
            resp = self._call_with_token_refresh(
                self._stub.GetDevice, _build, "GetDevice",
            )
        except grpc.RpcError as exc:
            code = exc.code() if hasattr(exc, "code") else None
            if code == grpc.StatusCode.NOT_FOUND:
                return None
            detail = exc.details() if hasattr(exc, "details") else str(exc)
            logger.error("grpc GetDevice failed: %s", detail)
            raise RuntimeError(f"GetDevice failed: {detail}") from exc

        d = resp.device
        logger.info("grpc GetDevice simei=%s device_id=%d status=%s", d.simei, d.device_id, d.status)
        return DeviceInfo(
            device_id=d.device_id,
            user_id=d.user_id,
            simei=d.simei,
            device_ip=d.device_ip,
            device_config=d.device_config,
            created_at=d.created_at,
            updated_at=d.updated_at,
            status=d.status or "active",
        )

    def update_token(self, new_token: str) -> None:
        """Update the auth token without rebuilding the gRPC channel."""
        self._token = new_token.strip()

    def close(self):
        """Close the gRPC channel."""
        self._channel.close()
        logger.info("platform grpc channel closed target=%s", self._target)


# ---------------------------------------------------------------------------
# Module-level shared client singleton — reuses gRPC channel across requests
# ---------------------------------------------------------------------------

_shared_client: PlatformClient | None = None
_shared_client_lock = threading.Lock()
_shared_client_token: str = ""


def get_shared_platform_client(auth_token: str) -> PlatformClient:
    """Get or create the module-level shared PlatformClient.

    The underlying gRPC channel is reused across requests to avoid
    repeated TCP + TLS handshake overhead.  When the *auth_token* changes
    (e.g. after re-login), the existing client's token is updated in-place
    without recreating the channel.

    Thread-safe: concurrent callers will receive the same instance.
    """
    global _shared_client, _shared_client_token

    token = auth_token.strip()

    # Fast path: client exists and token unchanged
    if _shared_client is not None and _shared_client_token == token:
        return _shared_client

    with _shared_client_lock:
        # Double-check after acquiring lock
        if _shared_client is not None:
            if _shared_client_token != token:
                _shared_client.update_token(token)
                _shared_client_token = token
                logger.info("shared platform client: token updated")
            return _shared_client

        # First creation — read platform defaults from config
        from config import get_config
        cfg = get_config()
        _shared_client = PlatformClient(
            grpc_target=cfg.platform.manager_grpc_target,
            auth_token=token,
            **cfg.platform.tls_kwargs,
        )
        _shared_client_token = token
        logger.info("shared platform client created target=%s", cfg.platform.manager_grpc_target)
        return _shared_client


def close_shared_platform_client() -> None:
    """Close the shared client (call during application shutdown)."""
    global _shared_client, _shared_client_token
    with _shared_client_lock:
        if _shared_client is not None:
            _shared_client.close()
            _shared_client = None
            _shared_client_token = ""
            logger.info("shared platform client closed")
