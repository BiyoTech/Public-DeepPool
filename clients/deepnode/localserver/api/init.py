"""设备初始化相关 API — 两步初始化架构。

核心设计: 设备注册与模型加载解耦。
  Step 1 (init_device): 获取配置 → 注册设备到 platform → 持久化凭证 → 启动日志上报
  Step 2 (后台异步):     下载并加载模型 → 建立 tunnel → 更新 platform 设备状态为 ready

关键约束: tunnel 连接必须在模型加载完成后才建立。
  如果 tunnel 在模型加载前就连接 nodemanager，nodemanager 可能立即分发推理任务，
  但此时引擎未就绪，会导致用户端推理失败或长时间阻塞。

这样即使模型下载/加载失败，设备仍然能被 platform 收集到注册信息。

simei 统一由 Python 设备指纹模块生成，无需外部传入。
"""

from __future__ import annotations

import json
import logging
import threading

from fastapi import APIRouter

from config import get_config
from rpc.platform_client import PlatformClient
from service.credential import DeviceCredential, save_credential
from service.device_fingerprint import get_cached_simei
from service.device_info import get_device_hardware_info
from service.manager import get_service_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/init", tags=["init"])


def _normalize_supported_models(payload: dict) -> list[str]:
    """提取并标准化支持的模型列表，列表为空则不传（由后端决定默认值）。"""
    supported = payload.get("supported_models")
    if isinstance(supported, list):
        return [str(item).strip().lower() for item in supported if str(item).strip()]
    return []


# ─────────── 设备初始化 API ───────────

@router.post("/device")
def init_device(payload: dict) -> dict:
    """两步初始化: 快速注册设备到 platform，然后异步加载模型。

    流程:
      1. 生成设备指纹 simei
      2. 通过 gRPC 获取平台下发的多模型部署配置列表
      3. 批量注册模型配置到 ServiceManager（不加载）
      4. 采集硬件信息，立即注册设备到 platform（init_stage="registering"）
      5. 持久化凭证、清理旧连接、启动日志上报
      6. 在后台线程中异步下载+加载第一个模型
      7. 模型就绪后建立 tunnel 连接 + 更新 platform 设备状态为 init_stage="ready"

    注意: tunnel 连接延迟到模型加载完成后才建立，避免 nodemanager 在引擎未就绪时
    分发推理任务导致用户端推理失败。

    前端收到响应后即可认为"设备已注册"，可通过 /api/init/status 轮询模型加载进度。
    """
    token = str(payload.get("token", "")).strip()
    cfg = get_config()

    if not token:
        logger.warning("init_device called without token")
        return {"code": 400, "message": "token is required"}

    try:
        simei = get_cached_simei()
    except RuntimeError as exc:
        logger.error("failed to generate device fingerprint: %s", exc)
        return {"code": 500, "message": f"fingerprint generation failed: {exc}"}

    supported_models = _normalize_supported_models(payload)
    logger.info("init_device start simei=%s supported_models=%s", simei, supported_models)

    platform_client = None
    try:
        platform_client = PlatformClient(
            grpc_target=cfg.platform.manager_grpc_target, auth_token=token,
        )

        # ── Step 1: 获取部署配置 ──
        deploy_configs = platform_client.get_multi_model_deploy_configs(
            simei=simei, supported_models=supported_models,
        )
        if not deploy_configs:
            logger.warning("init_device: platform returned no model configs")
            return {"code": 500, "message": "no model deploy config available"}

        # ── Step 2: 批量注册模型配置到 ServiceManager（仅写入注册表，不加载）──
        manager = get_service_manager()
        manager.register_models(deploy_configs)

        registered_models = [c.model_name for c in deploy_configs]

        # ── Step 3: 立即注册设备到 platform（init_stage="registering"）──
        # 不依赖模型加载结果，确保 platform 能收集到设备信息
        hw = get_device_hardware_info()
        device_config = {
            "init_stage": "registering",
            "simei": simei,
            "assigned_models": registered_models,
            "hardware": hw.to_dict(),
        }

        try:
            platform_client.register_device(
                simei=simei,
                device_ip="127.0.0.1",
                device_config=json.dumps(device_config, ensure_ascii=False),
                registered_models=registered_models,
            )
            logger.info("device registered to platform simei=%s models=%s", simei, registered_models)
        except RuntimeError as register_err:
            err_msg = str(register_err).lower()
            if "duplicate resource" in err_msg or "already exists" in err_msg:
                logger.warning("device already registered, continuing simei=%s", simei)
            else:
                raise

        # ── Step 4: 持久化凭证 + 日志上报 ──
        # 注意: tunnel 连接不在此处建立，而是延迟到模型加载完成后，
        # 避免 nodemanager 在引擎未就绪时分发推理任务。
        save_credential(DeviceCredential(simei=simei, token=token))

        _cleanup_existing_connections()
        _start_log_reporter(simei, token)

        # ── Step 5: 异步加载模型 + 加载完成后建立 tunnel（不阻塞 HTTP 响应）──
        first_cfg = deploy_configs[0]
        _start_async_model_loading(
            simei=simei,
            token=token,
            deploy_configs=deploy_configs,
            manager=manager,
        )

        logger.info(
            "init_device registered simei=%s models=%d, model loading in background",
            simei, len(deploy_configs),
        )
        return {
            "code": 0,
            "message": "ok",
            "data": {
                "device_ip": "127.0.0.1",
                "device_config": device_config,
                "model_loading": True,
            },
        }
    except Exception as exc:
        logger.exception("init_device failed simei=%s err=%s", simei, exc)
        return {
            "code": 500,
            "message": f"init failed: {exc}",
        }
    finally:
        if platform_client is not None:
            platform_client.close()


# ─────────── 异步模型加载 ───────────

def _start_async_model_loading(
    simei: str,
    token: str,
    deploy_configs: list,
    manager,
) -> None:
    """在后台线程中异步下载并加载第一个模型。

    加载完成后:
      1. 建立 nodemanager tunnel 连接（此时引擎已就绪，可安全接受推理任务）
      2. 更新 platform 设备配置为 init_stage="ready"
    加载失败仅记录日志，不影响设备注册状态。
    """
    def _load_worker():
        first_cfg = deploy_configs[0]
        logger.info("async model loading started: %s", first_cfg.model_name)

        try:
            running = manager.ensure_service(first_cfg)
            logger.info(
                "async model loaded: %s engine=%s rpc=%s:%d",
                running.model_name, running.engine_type,
                running.rpc_host, running.rpc_port,
            )

            # 模型就绪后才建立 tunnel 连接，确保 nodemanager 分发的推理任务能被正确处理
            _start_tunnel_connection(simei, token, running, manager)

            # 更新 platform 设备状态为 ready
            _update_device_status_to_ready(
                simei=simei,
                token=token,
                running=running,
                manager=manager,
                deploy_configs=deploy_configs,
            )
        except Exception as exc:
            logger.error(
                "async model loading failed: %s error=%s", first_cfg.model_name, exc,
                exc_info=True,
            )

    thread = threading.Thread(
        target=_load_worker,
        name="async-model-loader",
        daemon=True,
    )
    thread.start()


def _update_device_status_to_ready(
    simei: str,
    token: str,
    running,
    manager,
    deploy_configs: list,
) -> None:
    """模型加载完成后，更新 platform 上的设备配置为 ready 状态。"""
    cfg = get_config()
    platform_client = None
    try:
        platform_client = PlatformClient(
            grpc_target=cfg.platform.manager_grpc_target, auth_token=token,
        )

        hw = get_device_hardware_info()
        device_config = {
            "init_stage": "ready",
            "simei": simei,
            "llm_rpc_host": running.rpc_host,
            "llm_rpc_port": running.rpc_port,
            "llm_engine": running.engine_type,
            "assigned_models": [c.model_name for c in deploy_configs],
            "hardware": hw.to_dict(),
        }
        if manager.engine_config is not None:
            device_config["engine_config"] = manager.engine_config.to_dict()

        # 使用 UpdateDevice 更新设备信息（而非重新注册）
        try:
            platform_client.update_device(
                simei=simei,
                device_config=json.dumps(device_config, ensure_ascii=False),
            )
            logger.info("device status updated to ready simei=%s", simei)
        except Exception as update_err:
            # UpdateDevice 可能尚未实现，尝试 fallback 到 register_device（会触发 already exists）
            logger.warning("UpdateDevice failed (%s), trying re-register", update_err)
            try:
                platform_client.register_device(
                    simei=simei,
                    device_ip="127.0.0.1",
                    device_config=json.dumps(device_config, ensure_ascii=False),
                    registered_models=[c.model_name for c in deploy_configs],
                )
            except RuntimeError:
                logger.warning("re-register also failed, device status may stay as 'registering'")

    except Exception as exc:
        logger.warning("failed to update device status to ready: %s", exc)
    finally:
        if platform_client is not None:
            platform_client.close()


# ─────────── 停止服务 / 状态查询 ───────────

@router.post("/stop")
def stop_service() -> dict:
    """停止推理服务并断开 nodemanager 长连接。

    前端"暂停服务"按钮调用此接口，停止后用户需重新初始化才能恢复。
    在线状态由 NodeManager 实时连接管理，无需主动上报。
    """
    import main as main_module

    _stop_log_reporter()

    if main_module._tunnel_client is not None:
        logger.info("stop_service: disconnecting nodemanager tunnel")
        try:
            main_module._tunnel_client.stop()
        except Exception as exc:
            logger.warning("stop_service: tunnel stop error: %s", exc)
        main_module._tunnel_client = None

    manager = get_service_manager()
    manager.shutdown()
    logger.info("stop_service: inference service stopped")

    return {"code": 0, "message": "ok"}


@router.get("/status")
def init_status() -> dict:
    """查询本地推理服务状态（支持多模型）。

    返回所有已注册模型的状态信息，前端据此判断：
      - infer_ready=True  → 至少一个模型已加载，可以推理
      - infer_ready=False → 模型尚在加载或需要走设备初始化流程
      - models: 所有已注册模型的状态列表（包含 loading/loaded/error 等状态）
    """
    manager = get_service_manager()
    running = manager.get_running_service()
    models = manager.list_models()

    if running is None:
        return {
            "code": 0,
            "message": "ok",
            "data": {
                "infer_ready": False,
                "models": models,
            },
        }

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "infer_ready": True,
            "model_name": running.model_name,
            "engine_type": running.engine_type,
            "rpc_host": running.rpc_host,
            "rpc_port": running.rpc_port,
            "models": models,
        },
    }


# ─────────── 内部辅助函数 ───────────

def _cleanup_existing_connections() -> None:
    """关闭 auto-restore 可能已创建的旧 tunnel 和 log reporter。"""
    import main as main_module

    if main_module._tunnel_client is not None:
        logger.info("cleanup: stopping existing nodemanager tunnel before re-init")
        try:
            main_module._tunnel_client.stop()
        except Exception as exc:
            logger.warning("cleanup: tunnel stop error: %s", exc)
        main_module._tunnel_client = None

    if main_module._log_reporter is not None:
        logger.info("cleanup: stopping existing log reporter before re-init")
        try:
            main_module._log_reporter.stop()
        except Exception as exc:
            logger.warning("cleanup: log reporter stop error: %s", exc)
        main_module._log_reporter = None


def _start_tunnel_connection(simei: str, token: str, running, manager) -> None:
    """在模型加载完成后建立 nodemanager tunnel 连接。

    tunnel 连接必须在引擎就绪后建立，否则 nodemanager 可能在引擎未加载时
    分发推理任务，导致用户端推理失败。
    """
    try:
        import main as main_module
        from rpc.node_manager_client import NodeManagerClient

        cfg = get_config()
        client = NodeManagerClient(
            grpc_target=cfg.platform.nodemanager_grpc_target,
            simei=simei,
            auth_token=token,
            model_name=running.model_name,
            engine_type=running.engine_type,
            service_manager=manager,
        )
        client.start()

        main_module._tunnel_client = client

        # 绑定错误日志上报 Handler 到 tunnel 客户端
        from log_setup import get_error_handler
        _err_handler = get_error_handler()
        if _err_handler is not None:
            _err_handler.bind(client)

        logger.info(
            "nodemanager tunnel started (model ready) simei=%s model=%s",
            simei, running.model_name,
        )
    except Exception as exc:
        logger.warning("failed to start nodemanager tunnel: %s", exc)


def _start_log_reporter(simei: str, token: str) -> None:
    """启动推理日志定时上报后台线程。"""
    try:
        import main as main_module
        from service.log_reporter import LogReporter
        from service.statistics import get_statistics_db

        cfg = get_config()
        reporter = LogReporter(
            stats_db=get_statistics_db(),
            platform_client=PlatformClient(
                grpc_target=cfg.platform.manager_grpc_target, auth_token=token,
            ),
            simei=simei,
        )
        reporter.start()

        main_module._log_reporter = reporter
        logger.info("LogReporter started simei=%s", simei)
    except Exception as exc:
        logger.warning("failed to start LogReporter: %s", exc)


def _stop_log_reporter() -> None:
    """停止推理日志上报后台线程。"""
    try:
        import main as main_module
        if main_module._log_reporter is not None:
            logger.info("stop_service: stopping log reporter")
            main_module._log_reporter.stop()
            main_module._log_reporter = None
    except Exception as exc:
        logger.warning("stop_service: log reporter stop error: %s", exc)
