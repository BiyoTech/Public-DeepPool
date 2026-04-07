"""用户认证与设备查询 API — 通过 gRPC 与 Platform Manager 交互。

替代原 platform_proxy.py 的 HTTP 反向代理，所有与 Manager 的通信
统一走 gRPC，消除 HTTP 端口依赖和 CORS 问题。

端点:
  POST /api/auth/login       → gRPC Login
  POST /api/auth/register    → gRPC RegisterUser
  GET  /api/device/check/{simei} → gRPC GetDevice
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header
from pydantic import BaseModel

from config import get_config
from rpc.platform_client import PlatformClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


# ─── 请求/响应模型 ───


class LoginBody(BaseModel):
    account: str
    password: str


class RegisterBody(BaseModel):
    username: str
    password: str
    phone: str
    email: str
    identity: str = ""
    user_type: str = ""


# ─── 端点 ───


@router.post("/api/auth/login")
def auth_login(body: LoginBody) -> dict:
    """用户登录 — 通过 gRPC 调用 Manager Login。"""
    cfg = get_config()
    client = PlatformClient(grpc_target=cfg.platform.manager_grpc_target, auth_token="")
    try:
        result = client.login(account=body.account, password=body.password)
        return {"code": 0, "message": "ok", "data": result}
    except RuntimeError as exc:
        logger.warning("auth_login failed: %s", exc)
        return {"code": 401, "message": str(exc)}
    finally:
        client.close()


@router.post("/api/auth/register")
def auth_register(body: RegisterBody) -> dict:
    """用户注册 — 通过 gRPC 调用 Manager RegisterUser。"""
    cfg = get_config()
    client = PlatformClient(grpc_target=cfg.platform.manager_grpc_target, auth_token="")
    try:
        user = client.register_user(
            username=body.username,
            password=body.password,
            phone=body.phone,
            email=body.email,
            identity=body.identity,
            user_type=body.user_type,
        )
        return {"code": 0, "message": "ok", "data": user}
    except RuntimeError as exc:
        logger.warning("auth_register failed: %s", exc)
        return {"code": 400, "message": str(exc)}
    finally:
        client.close()


@router.get("/api/device/check/{simei}")
def device_check(simei: str, authorization: str = Header(default="")) -> dict:
    """查询设备是否已注册 — 通过 gRPC 调用 Manager GetDevice。

    前端通过 Authorization header 传入 Bearer token。
    """
    # 提取 token（去掉 "Bearer " 前缀）
    token = authorization.replace("Bearer ", "").strip() if authorization else ""
    if not token:
        return {"code": 401, "message": "authorization required"}

    cfg = get_config()
    client = PlatformClient(grpc_target=cfg.platform.manager_grpc_target, auth_token=token)
    try:
        device = client.get_device(simei)
        if device is None:
            return {"code": 404, "message": "device not found"}
        return {"code": 0, "message": "ok", "data": {"simei": device.simei, "device_id": device.device_id}}
    except RuntimeError as exc:
        logger.warning("device_check failed: %s", exc)
        return {"code": 500, "message": str(exc)}
    finally:
        client.close()
