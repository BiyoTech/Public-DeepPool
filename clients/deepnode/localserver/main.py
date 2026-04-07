"""DeepNode 本地服务入口，提供设备初始化等本地 API。

支持两种运行模式：
  - Tauri sidecar 模式：由 Tauri 桌面应用启动，simei 由 Python 生成
  - Standalone 独立模式：通过命令行启动，自动生成 simei + 自动初始化

启动时自动尝试恢复推理服务：读取持久化的设备凭证，
向 platform 请求模型部署配置并启动 gRPC 推理服务。
推理服务就绪后自动与 nodemanager 建立双向流长连接，
接收远程推理任务并回传结果。
若凭证不存在或 platform 未返回可用模型，则等待前端触发设备初始化。
"""

import argparse
import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import init_config
from log_setup import setup_logging
from api import init_router, stats_router, dashboard_router, auth_router


def _parse_cli_args() -> argparse.Namespace:
    """解析命令行参数，支持独立运行模式。"""
    parser = argparse.ArgumentParser(
        description="DeepNode Local Worker — 推理节点本地服务",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="配置文件路径（默认：localserver/config.yaml）",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        default=False,
        help="启用独立运行模式（自动生成 simei + 自动初始化）",
    )
    parser.add_argument(
        "--token", "-t",
        type=str,
        default=None,
        help="Platform 认证 token（覆盖配置文件中的 standalone.token）",
    )
    parser.add_argument(
        "--account", "-a",
        type=str,
        default=None,
        help="Platform 登录账号（覆盖配置文件中的 standalone.account）",
    )
    parser.add_argument(
        "--password", "-p",
        type=str,
        default=None,
        help="Platform 登录密码（覆盖配置文件中的 standalone.password）",
    )
    # 使用 parse_known_args 忽略 PyInstaller bootloader 注入的未知参数（-B -S -I）
    args, _ = parser.parse_known_args()
    return args


# 解析 CLI 参数
_cli_args = _parse_cli_args()

# 加载配置（CLI --config 优先）
cfg = init_config(path=_cli_args.config)

# CLI 参数覆盖配置文件
if _cli_args.standalone:
    cfg.standalone.enabled = True
if _cli_args.token:
    cfg.standalone.token = _cli_args.token
if _cli_args.account:
    cfg.standalone.account = _cli_args.account
if _cli_args.password:
    cfg.standalone.password = _cli_args.password

# 初始化日志
setup_logging(
    level=cfg.log.level,
    log_dir=cfg.log.log_dir,
    file_name=cfg.log.file_name,
    backup_count=cfg.log.backup_count,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="DeepNode Local Worker")

# 允许前端跨域访问（本地服务与前端分属不同端口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(init_router)
app.include_router(stats_router)
app.include_router(dashboard_router)
app.include_router(auth_router)

# 如果探测到 Vue SPA 构建产物，挂载静态文件中间件（托管 JS/CSS/图片等资源）
from api.dashboard import get_web_dist_dir

_web_dist = get_web_dist_dir()
if _web_dist is not None:
    from fastapi.staticfiles import StaticFiles
    # 挂载 /assets（Vite 构建产物的静态资源目录）
    assets_dir = _web_dist / 'assets'
    if assets_dir.is_dir():
        app.mount('/assets', StaticFiles(directory=str(assets_dir)), name='vue-assets')
        logger.info("mounted Vue SPA assets from %s", assets_dir)
    # 兜底：其他静态文件（favicon.ico 等）直接从根目录挂载
    app.mount('/static', StaticFiles(directory=str(_web_dist)), name='vue-static')
    logger.info("Vue SPA web UI enabled at http://127.0.0.1:%d/", cfg.server.port)

# 全局 nodemanager 长连接客户端引用，供 shutdown 时关闭
_tunnel_client = None
# 全局日志上报器引用
_log_reporter = None


@app.get("/health")
def health() -> dict:
    """健康检查"""
    return {"status": "ok", "service": "deepnode-local-worker"}


# ─────────────────────────────────────────────────
# 启动时自动尝试恢复推理服务并建立 nodemanager 长连接
# ─────────────────────────────────────────────────

def _try_restore_and_connect() -> None:
    """尝试恢复推理服务，成功后与 nodemanager 建立长连接并启动日志上报。

    恢复策略：
      1. 读取凭证 → 获取部署配置 → 注册模型 → 启动日志上报
      2. 加载第一个模型（同步，在当前 daemon 线程中执行）
      3. 模型就绪后才建立 nodemanager tunnel 连接

    tunnel 必须在模型加载完成后建立，否则 nodemanager 可能在引擎未就绪时
    分发推理任务，导致用户端推理失败。

    任何环节失败仅记录日志，不阻塞 HTTP 服务启动。
    """
    global _tunnel_client, _log_reporter

    from service.credential import load_credential
    from rpc.platform_client import PlatformClient
    from rpc.node_manager_client import NodeManagerClient
    from service.manager import get_service_manager
    from service.log_reporter import LogReporter
    from service.statistics import get_statistics_db

    cred = load_credential()
    if cred is None:
        logger.info("no device credential found, skip auto-restore (waiting for init_device)")
        return

    logger.info("auto-restore: found credential simei=%s, requesting deploy configs from platform", cred.simei)

    platform_grpc_target = cfg.platform.manager_grpc_target
    platform_client = None
    try:
        platform_client = PlatformClient(grpc_target=platform_grpc_target, auth_token=cred.token)

        # 获取多模型部署配置列表
        deploy_configs = platform_client.get_multi_model_deploy_configs(
            simei=cred.simei,
            supported_models=[],
        )
        if not deploy_configs:
            logger.warning("auto-restore: platform returned no model configs, skip")
            return

        # Step 1: 批量注册模型配置 + 启动日志上报
        manager = get_service_manager()
        manager.register_models(deploy_configs)

        _log_reporter = LogReporter(
            stats_db=get_statistics_db(),
            platform_client=PlatformClient(grpc_target=platform_grpc_target, auth_token=cred.token),
            simei=cred.simei,
        )
        _log_reporter.start()

        logger.info("auto-restore: log reporter started, registered=%d models", len(deploy_configs))

        # Step 2: 加载第一个模型（同步阻塞，在 daemon 线程中执行不影响 HTTP 服务）
        first_cfg = deploy_configs[0]
        try:
            running = manager.ensure_service(first_cfg)
            logger.info(
                "auto-restore: model loaded model=%s engine=%s rpc=%s:%d",
                running.model_name, running.engine_type,
                running.rpc_host, running.rpc_port,
            )
        except Exception as model_exc:
            logger.warning("auto-restore: model loading failed (device still registered): %s", model_exc)
            return

        # Step 3: 模型就绪后才建立 tunnel 连接
        _tunnel_client = NodeManagerClient(
            grpc_target=cfg.platform.nodemanager_grpc_target,
            simei=cred.simei,
            auth_token=cred.token,
            model_name=running.model_name,
            engine_type=running.engine_type,
            service_manager=manager,
        )
        _tunnel_client.start()

        # 绑定错误日志上报 Handler 到 tunnel 客户端
        from log_setup import get_error_handler
        _err_handler = get_error_handler()
        if _err_handler is not None:
            _err_handler.bind(_tunnel_client)

        logger.info("auto-restore: tunnel connected (model ready) simei=%s", cred.simei)

    except Exception as exc:
        logger.warning("auto-restore: failed: %s", exc)
    finally:
        if platform_client is not None:
            platform_client.close()


def _resolve_standalone_token() -> str | None:
    """解析 standalone 模式的认证 token。

    优先级：直接提供的 token > 通过 account/password 自动登录获取。
    返回 None 表示无法获取 token。
    """
    # 优先使用直接提供的 token
    token = cfg.standalone.token.strip()
    if token:
        logger.info("standalone: using pre-configured token")
        return token

    # 尝试通过 account/password 自动登录
    account = cfg.standalone.account.strip()
    password = cfg.standalone.password.strip()

    if not account or not password:
        logger.error(
            "standalone mode requires either --token or --account/--password. "
            "Example: ./deepnode-server --standalone --account myuser --password mypass"
        )
        return None

    logger.info("standalone: logging in with account=%s ...", account)
    try:
        from service.platform_auth import platform_login
        result = platform_login(account=account, password=password)
        # 将获取到的 token 回写到配置，供后续流程使用
        cfg.standalone.token = result.token
        logger.info("standalone: login success, user=%s (id=%d)", result.username, result.user_id)
        return result.token
    except RuntimeError as exc:
        logger.error("standalone: login failed: %s", exc)
        return None


def _standalone_auto_init() -> None:
    """独立运行模式自治启动：自动认证 → 自动生成 simei → 自动完成设备初始化。

    等同于用户在前端完成"登录 + 加入网络"，但完全由 localserver 自主完成。
    """
    from api.init import init_device

    token = _resolve_standalone_token()
    if not token:
        return

    # 调用 init_device API 内部逻辑完成初始化（simei 由其内部自动生成）
    logger.info("standalone: auto-initializing device...")
    result = init_device({"token": token, "supported_models": []})
    logger.info("standalone: init_device result: %s", result)


@app.on_event("startup")
def on_startup():
    """FastAPI 启动事件：根据模式选择启动策略。

    - standalone 模式：自动生成 simei + 自动完成设备初始化
    - sidecar/普通模式：尝试从持久化凭证恢复推理服务
    """
    if cfg.standalone.enabled:
        logger.info("standalone mode enabled, starting auto-init...")
        thread = threading.Thread(
            target=_standalone_auto_init,
            name="standalone-auto-init",
            daemon=True,
        )
    else:
        thread = threading.Thread(
            target=_try_restore_and_connect,
            name="infer-auto-restore",
            daemon=True,
        )
    thread.start()
    logger.info("startup thread started (standalone=%s)", cfg.standalone.enabled)


@app.on_event("shutdown")
def on_shutdown():
    """FastAPI 关停事件：断开长连接、停止日志上报并关停推理服务。"""
    global _tunnel_client, _log_reporter

    # 设备在线状态由 NodeManager 实时连接管理，无需主动上报 stopped

    if _log_reporter is not None:
        logger.info("shutting down log reporter")
        _log_reporter.stop()
        _log_reporter = None

    if _tunnel_client is not None:
        logger.info("shutting down nodemanager tunnel connection")
        _tunnel_client.stop()
        _tunnel_client = None

    # 关停推理引擎和 gRPC server，释放 GPU 资源
    from service.manager import get_service_manager
    get_service_manager().shutdown()

    # 关闭统计数据库
    from service.statistics import get_statistics_db
    get_statistics_db().close()

    logger.info("inference service shutdown complete")


if __name__ == "__main__":
    import uvicorn

    logger.info(
        "Starting local server on %s:%d (standalone=%s, manager_grpc=%s, nodemanager_grpc=%s)",
        cfg.server.host,
        cfg.server.port,
        cfg.standalone.enabled,
        cfg.platform.manager_grpc_target,
        cfg.platform.nodemanager_grpc_target,
    )
    uvicorn.run(app, host=cfg.server.host, port=cfg.server.port)
