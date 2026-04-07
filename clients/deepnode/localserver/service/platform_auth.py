"""Platform gRPC 认证模块。

封装 Platform Manager 的 Login gRPC 调用，供 standalone 模式自动获取 token。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import get_config
from rpc.platform_client import PlatformClient

logger = logging.getLogger(__name__)


@dataclass
class LoginResult:
    """登录成功后的结果。"""
    token: str
    user_id: int
    username: str


def platform_login(account: str, password: str) -> LoginResult:
    """通过 gRPC 调用 Platform Manager Login 获取认证 token。

    Args:
        account:  登录账号（用户名/手机号/邮箱）。
        password: 登录密码。

    Returns:
        LoginResult 包含 token 和用户基本信息。

    Raises:
        RuntimeError: 登录失败。
    """
    cfg = get_config()
    # Login RPC 不需要 auth_token，传空字符串
    client = PlatformClient(
        grpc_target=cfg.platform.manager_grpc_target,
        auth_token="",
    )

    try:
        result = client.login(account=account, password=password)
    finally:
        client.close()

    user = result.get("user", {})
    login_result = LoginResult(
        token=result["token"],
        user_id=int(user.get("id", 0)),
        username=str(user.get("username", "")),
    )

    logger.info(
        "platform_login: success user_id=%d username=%s",
        login_result.user_id, login_result.username,
    )
    return login_result
