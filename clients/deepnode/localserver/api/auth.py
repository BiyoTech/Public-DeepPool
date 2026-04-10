"""User authentication and device query API — via shared gRPC PlatformClient.

All communication with Platform Manager goes through gRPC (no HTTP proxy).
Uses the module-level shared PlatformClient for connection reuse.

Endpoints:
  POST /api/auth/login       → gRPC Login
  POST /api/auth/register    → gRPC RegisterUser
  GET  /api/device/check/{simei} → gRPC GetDevice
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from rpc.platform_client import PlatformClient, get_shared_platform_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


# --- Request / Response models ---


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


# --- Endpoints ---


@router.post("/api/auth/login")
def auth_login(body: LoginBody) -> dict:
    """User login — gRPC Login via shared PlatformClient.

    Returns HTTP 401 on authentication failure so that the frontend
    ``safeFetch`` interceptor can trigger automatic logout.
    """
    from config import get_config
    cfg = get_config()
    # Login does not require auth_token; create a lightweight temporary client
    client = PlatformClient(
        grpc_target=cfg.platform.manager_grpc_target, auth_token="",
        **cfg.platform.tls_kwargs,
    )
    try:
        result = client.login(account=body.account, password=body.password)
        return {"code": 0, "message": "ok", "data": result}
    except RuntimeError as exc:
        logger.warning("auth_login failed: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc))
    finally:
        client.close()


@router.post("/api/auth/register")
def auth_register(body: RegisterBody) -> dict:
    """User registration — gRPC RegisterUser via shared PlatformClient."""
    from config import get_config
    cfg = get_config()
    client = PlatformClient(
        grpc_target=cfg.platform.manager_grpc_target, auth_token="",
        **cfg.platform.tls_kwargs,
    )
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
    """Check whether a device is registered — gRPC GetDevice via shared client.

    Frontend passes the Bearer token via Authorization header.
    Returns HTTP 401 when the token is missing or invalid.
    """
    token = authorization.replace("Bearer ", "").strip() if authorization else ""
    if not token:
        raise HTTPException(status_code=401, detail="authorization required")

    client = get_shared_platform_client(token)
    try:
        device = client.get_device(simei)
        if device is None:
            return {"code": 404, "message": "device not found"}
        return {"code": 0, "message": "ok", "data": {"simei": device.simei, "device_id": device.device_id}}
    except RuntimeError as exc:
        logger.warning("device_check failed: %s", exc)
        # Token-related failures surface as 401 to trigger frontend logout
        err_msg = str(exc).lower()
        if "unauthenticated" in err_msg or "permission" in err_msg or "token" in err_msg:
            raise HTTPException(status_code=401, detail=str(exc))
        return {"code": 500, "message": str(exc)}
