"""多模型服务管理器 — 按需加载 + LRU 淘汰。

核心设计：
  - ModelSlot: 模型注册表中的单条记录（配置 + 引擎 + 状态）
  - ServiceManager: 多引擎注册表，根据 model_name 按需加载/卸载引擎
  - LRU 策略: 使用 OrderedDict，每次访问 move_to_end，淘汰时 popitem(last=False)
  - 内存守卫: 加载前检查可用内存，不足时触发 LRU 淘汰

所有模型配置由 platform manager 下发，客户端根据系统平台自动选择推理后端。
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum

from config import EngineConfig, MultiModelConfig, get_config
from engine.base import LLMEngine
from engine.selector import detect_engine_type
from model.downloader import download_model_hf
from model.registry import resolve_model_dir
from rpc.platform_client import ModelDeployConfig
from service.memory_guard import get_available_memory_gb, has_enough_memory

logger = logging.getLogger(__name__)

# gRPC server 优雅关停超时（秒）
_GRPC_SHUTDOWN_TIMEOUT = 5


class ModelState(str, Enum):
    """模型生命周期状态。"""
    REGISTERED = "registered"    # 已注册配置，尚未加载
    LOADING = "loading"          # 正在下载/加载中
    LOADED = "loaded"            # 已加载，可用于推理
    UNLOADING = "unloading"      # 正在卸载中
    ERROR = "error"              # 加载失败


@dataclass
class ModelSlot:
    """模型注册表中的单条记录。

    Attributes:
        model_name:    模型名称（唯一标识）
        deploy_config: 平台下发的部署配置
        engine:        推理引擎实例（已加载时非 None）
        engine_type:   引擎类型标识
        engine_config: 引擎性能配置
        state:         当前状态
        last_accessed: 最后访问时间戳（LRU 淘汰依据）
        error_msg:     最近一次错误信息
    """
    model_name: str
    deploy_config: ModelDeployConfig
    engine: LLMEngine | None = None
    engine_type: str = ""
    engine_config: EngineConfig | None = None
    state: ModelState = ModelState.REGISTERED
    last_accessed: float = 0.0
    error_msg: str = ""
    # 模型粒度锁，保证同一模型不会被并发加载
    _load_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


def _create_engine(
    engine_type: str,
    engine_config: EngineConfig,
    options: dict | None = None,
) -> LLMEngine:
    """根据引擎类型创建推理引擎实例。

    按平台差异化处理：
      - vllm_mlx: MLX Metal 加速（macOS M 系列）
      - vllm:     NVIDIA GPU（Linux）
      - llamacpp:  GGUF 量化模型
    """
    opts = options or {}
    engine_type = engine_type.strip().lower()

    if engine_type == "vllm_mlx":
        from engine.vllm_mlx import VLLMMLXEngine
        return VLLMMLXEngine(engine_config=engine_config)

    if engine_type == "vllm":
        from engine.vllm_engine import VLLMEngine
        return VLLMEngine(engine_config=engine_config)

    if engine_type == "llamacpp":
        from engine.llamacpp import LlamaCppEngine
        n_gpu_layers = int(opts.get("n_gpu_layers", -1))
        n_ctx = engine_config.max_kv_size if engine_config.max_kv_size > 0 else int(opts.get("n_ctx", 4096))
        return LlamaCppEngine(
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            engine_config=engine_config,
        )

    raise ValueError(
        f"unknown engine type: {engine_type}. "
        f"Supported: vllm_mlx, vllm, llamacpp"
    )


@dataclass
class RunningService:
    """对外暴露的运行服务快照信息。"""
    model_name: str
    engine_type: str
    rpc_host: str
    rpc_port: int
    started_at: float


class ServiceManager:
    """多模型服务管理器 — 注册表 + LRU 淘汰 + 按需加载。

    职责：
      - 管理多个模型的注册、加载、卸载生命周期
      - 根据 model_name 路由到对应引擎
      - 内存不足时按 LRU 策略自动淘汰最久未使用的模型
      - 管理共享的 gRPC server（所有模型共用一个端口）
    """

    def __init__(self):
        # 注册表：OrderedDict 维护 LRU 顺序，尾部是最近使用的
        self._slots: OrderedDict[str, ModelSlot] = OrderedDict()
        self._lock = threading.Lock()

        # 共享 gRPC server（所有模型共用）
        self._grpc_server = None
        self._grpc_host: str = ""
        self._grpc_port: int = 0

        # 多模型管理配置
        self._multi_model_cfg: MultiModelConfig = get_config().multi_model
        logger.info(
            "ServiceManager initialized: max_loaded_models=%d memory_reserve_gb=%.1f",
            self._multi_model_cfg.max_loaded_models,
            self._multi_model_cfg.memory_reserve_gb,
        )

    # ─────────── 模型注册 ───────────

    def register_model(self, deploy_cfg: ModelDeployConfig) -> None:
        """注册模型配置到注册表（不加载）。

        若模型已注册，更新其配置。
        """
        with self._lock:
            name = deploy_cfg.model_name
            if name in self._slots:
                slot = self._slots[name]
                slot.deploy_config = deploy_cfg
                logger.info("model config updated: %s", name)
            else:
                self._slots[name] = ModelSlot(
                    model_name=name,
                    deploy_config=deploy_cfg,
                )
                logger.info("model registered: %s (repo=%s)", name, deploy_cfg.repo_id)

    def register_models(self, configs: list[ModelDeployConfig]) -> None:
        """批量注册模型配置。"""
        for cfg in configs:
            self.register_model(cfg)
        logger.info("batch registered %d models", len(configs))

    def sync_models(self, configs: list[ModelDeployConfig]) -> None:
        """同步模型注册表：新增/更新平台下发的模型，移除不再分配的旧模型。

        适用于管理员调整模型分配后的重载场景，确保本地注册表与平台分配保持一致。
        被移除的模型如果已加载，会先卸载引擎释放资源。
        """
        new_names = {cfg.model_name for cfg in configs}

        # 1. 找出需要移除的旧模型（本地有、平台不再分配的）
        with self._lock:
            old_names = set(self._slots.keys())
        removed_names = old_names - new_names

        # 2. 卸载并移除不再分配的模型
        for name in removed_names:
            with self._lock:
                slot = self._slots.get(name)
            if slot is not None:
                if slot.state == ModelState.LOADED and slot.engine is not None:
                    logger.info("sync_models: unloading removed model: %s", name)
                    self._unload_slot(slot)
                with self._lock:
                    self._slots.pop(name, None)
                logger.info("sync_models: removed model: %s", name)

        # 3. 注册/更新平台下发的模型
        self.register_models(configs)

        logger.info(
            "sync_models: synced %d models (added/updated=%d, removed=%d)",
            len(configs), len(new_names - old_names), len(removed_names),
        )

    # ─────────── 引擎获取（核心路由） ───────────

    def get_or_load_engine(self, model_name: str) -> LLMEngine:
        """获取指定模型的推理引擎，未加载则按需加载。

        这是所有推理请求的统一入口：
          1. 已加载 → 直接返回引擎，更新 LRU 访问时间
          2. 已注册未加载 → 检查内存、必要时淘汰、下载并加载模型
          3. 未注册 → 抛出 ValueError

        Args:
            model_name: 请求的模型名称

        Returns:
            就绪的 LLMEngine 实例

        Raises:
            ValueError: 模型未注册
            RuntimeError: 加载失败（内存不足 / 引擎错误）
        """
        with self._lock:
            if model_name not in self._slots:
                available = list(self._slots.keys())
                raise ValueError(
                    f"model '{model_name}' not registered. "
                    f"Available: {available}"
                )

            slot = self._slots[model_name]

            # 已加载且引擎就绪 → 快速路径
            if slot.state == ModelState.LOADED and slot.engine is not None and slot.engine.ready:
                slot.last_accessed = time.time()
                self._slots.move_to_end(model_name)  # LRU: 移到尾部（最近使用）
                logger.debug("engine cache hit: %s", model_name)
                return slot.engine

            # 正在加载中 → 等待（释放全局锁，通过模型粒度锁等待）
            if slot.state == ModelState.LOADING:
                load_lock = slot._load_lock
        # 如果正在加载，在全局锁外等待模型粒度锁
        if slot.state == ModelState.LOADING:
            logger.info("waiting for model loading: %s", model_name)
            with slot._load_lock:
                # 加载完成后重新检查状态
                if slot.state == ModelState.LOADED and slot.engine is not None:
                    slot.last_accessed = time.time()
                    return slot.engine
                if slot.state == ModelState.ERROR:
                    raise RuntimeError(f"model '{model_name}' load failed: {slot.error_msg}")

        # 需要加载 → 获取模型粒度锁
        return self._load_model(slot)

    def _load_model(self, slot: ModelSlot) -> LLMEngine:
        """执行模型加载（下载 + 创建引擎 + load）。

        通过模型粒度锁保证同一模型不会被并发加载两次，
        同时不阻塞其他已加载模型的推理请求。
        """
        with slot._load_lock:
            # Double-check: 另一个线程可能已经完成加载
            if slot.state == ModelState.LOADED and slot.engine is not None and slot.engine.ready:
                slot.last_accessed = time.time()
                return slot.engine

            slot.state = ModelState.LOADING
            slot.error_msg = ""
            cfg = slot.deploy_config

            logger.info("loading model: %s (repo=%s)", slot.model_name, cfg.repo_id)

            try:
                # 加载前确保有足够内存
                self._ensure_memory_for_new_model()

                # 确定引擎类型
                engine_type = (cfg.engine or "").strip().lower()
                if not engine_type:
                    engine_type = detect_engine_type()

                # 获取并填充引擎配置
                engine_config = EngineConfig(**get_config().engine.to_dict())
                engine_config.auto_fill_defaults(engine_type=engine_type)

                # 解析模型目录并下载
                model_dir = resolve_model_dir(cfg.model_name, cfg.model_base_dir)
                model_path = download_model_hf(
                    repo_id=cfg.repo_id,
                    local_dir=model_dir,
                )
                logger.info("model downloaded: %s path=%s", slot.model_name, model_path)

                # 创建引擎并加载（失败时自动修复模型缓存并重试一次）
                engine = _create_engine(engine_type, engine_config, cfg.options)
                try:
                    engine.load(model_name=cfg.model_name, model_path=model_path)
                except Exception as load_exc:
                    logger.warning(
                        "model load failed, attempting repair & retry: %s error=%s",
                        slot.model_name, load_exc,
                    )
                    # 修复损坏/缺失的模型文件（只重新下载缺失部分）
                    from model.downloader import repair_model_cache
                    model_path = repair_model_cache(
                        repo_id=cfg.repo_id,
                        local_dir=model_dir,
                    )
                    # 复用已有引擎实例重试加载（不重建！）
                    # 重建引擎会触发 mlx C 扩展的二次初始化，导致 nanobind abort。
                    engine.load(model_name=cfg.model_name, model_path=model_path)

                # 更新 slot 状态
                slot.engine = engine
                slot.engine_type = engine_type
                slot.engine_config = engine_config
                slot.state = ModelState.LOADED
                slot.last_accessed = time.time()

                # LRU: 移到尾部
                with self._lock:
                    if slot.model_name in self._slots:
                        self._slots.move_to_end(slot.model_name)

                logger.info(
                    "model loaded successfully: %s engine=%s available_memory=%.1fGB",
                    slot.model_name, engine_type, get_available_memory_gb(),
                )

                # 确保 gRPC server 已启动
                self._ensure_grpc_server(cfg, engine_config)

                return engine

            except Exception as exc:
                slot.state = ModelState.ERROR
                slot.error_msg = str(exc)
                logger.error("model load failed: %s error=%s", slot.model_name, exc, exc_info=True)
                raise RuntimeError(f"failed to load model '{slot.model_name}': {exc}") from exc

    # ─────────── 内存管理与 LRU 淘汰 ───────────

    def _ensure_memory_for_new_model(self) -> None:
        """加载新模型前确保内存充足，必要时触发 LRU 淘汰。

        策略：
          1. 检查已加载模型数是否达到上限 → 淘汰最久未用
          2. 检查可用内存是否低于保留阈值 → 淘汰最久未用
          3. 淘汰后仍不满足条件 → 抛出 RuntimeError
        """
        max_loaded = self._multi_model_cfg.max_loaded_models
        reserve_gb = self._multi_model_cfg.memory_reserve_gb

        # 检查已加载模型数量上限
        if max_loaded > 0:
            loaded_count = self._count_loaded_models()
            while loaded_count >= max_loaded:
                evicted = self._evict_lru_model()
                if not evicted:
                    raise RuntimeError(
                        f"cannot load new model: already at max ({max_loaded}) "
                        f"and no model can be evicted"
                    )
                loaded_count = self._count_loaded_models()

        # 检查可用内存
        if reserve_gb > 0:
            attempts = 0
            max_attempts = self._count_loaded_models() + 1  # 最多淘汰所有已加载模型
            while not has_enough_memory(reserve_gb) and attempts < max_attempts:
                evicted = self._evict_lru_model()
                if not evicted:
                    break
                attempts += 1

            if not has_enough_memory(reserve_gb):
                available = get_available_memory_gb()
                logger.warning(
                    "memory still insufficient after eviction: available=%.1fGB reserve=%.1fGB",
                    available, reserve_gb,
                )
                # 内存不足但仍尝试加载（让 OS 的虚拟内存机制兜底），仅发出警告

    def _count_loaded_models(self) -> int:
        """统计当前已加载的模型数量。"""
        with self._lock:
            return sum(
                1 for s in self._slots.values()
                if s.state == ModelState.LOADED and s.engine is not None
            )

    def _evict_lru_model(self) -> bool:
        """淘汰最近最少使用的模型，释放内存。

        Returns:
            True 表示成功淘汰了一个模型，False 表示无模型可淘汰。
        """
        with self._lock:
            # 从 OrderedDict 头部开始找已加载的模型（头部 = 最久未用）
            for name, slot in self._slots.items():
                if slot.state == ModelState.LOADED and slot.engine is not None:
                    target_slot = slot
                    break
            else:
                logger.info("no loaded model to evict")
                return False

        # 在全局锁外执行卸载（卸载可能耗时）
        return self._unload_slot(target_slot)

    def _unload_slot(self, slot: ModelSlot) -> bool:
        """卸载指定模型的引擎，释放资源。"""
        slot.state = ModelState.UNLOADING
        logger.info("evicting model: %s (last_accessed=%.0f)", slot.model_name, slot.last_accessed)

        try:
            if slot.engine is not None:
                slot.engine.unload()
        except Exception as exc:
            logger.warning("engine unload error for %s: %s", slot.model_name, exc)

        slot.engine = None
        slot.engine_config = None
        slot.state = ModelState.REGISTERED
        logger.info("model evicted: %s, available_memory=%.1fGB", slot.model_name, get_available_memory_gb())
        return True

    # ─────────── gRPC Server 管理 ───────────

    def _ensure_grpc_server(self, cfg: ModelDeployConfig, engine_config: EngineConfig) -> None:
        """确保共享 gRPC server 已启动。

        多模型共用一个 gRPC server，Servicer 通过 ServiceManager 路由。
        """
        with self._lock:
            if self._grpc_server is not None:
                return

            from rpc.infer_server import start_grpc_server
            self._grpc_server = start_grpc_server(
                service_manager=self,
                host=cfg.rpc_host,
                port=cfg.rpc_port,
                max_workers=engine_config.num_workers,
            )
            self._grpc_host = cfg.rpc_host
            self._grpc_port = cfg.rpc_port
            logger.info("shared gRPC server started at %s:%d", cfg.rpc_host, cfg.rpc_port)

    # ─────────── 查询接口 ───────────

    def get_running_service(self) -> RunningService | None:
        """返回第一个已加载模型的运行信息（向后兼容）。"""
        with self._lock:
            for slot in reversed(self._slots.values()):  # 从最近使用的开始
                if slot.state == ModelState.LOADED and slot.engine is not None:
                    return RunningService(
                        model_name=slot.model_name,
                        engine_type=slot.engine_type,
                        rpc_host=self._grpc_host,
                        rpc_port=self._grpc_port,
                        started_at=slot.last_accessed,
                    )
        return None

    def list_models(self) -> list[dict]:
        """返回所有已注册模型的状态信息，供 status API 使用。"""
        with self._lock:
            result = []
            for name, slot in self._slots.items():
                result.append({
                    "model_name": name,
                    "state": slot.state.value,
                    "engine_type": slot.engine_type,
                    "last_accessed": slot.last_accessed,
                    "error_msg": slot.error_msg,
                })
            return result

    @property
    def engine_config(self) -> EngineConfig | None:
        """返回最近使用的模型的 EngineConfig，供 device_config 上报。"""
        with self._lock:
            for slot in reversed(self._slots.values()):
                if slot.engine_config is not None:
                    return slot.engine_config
        return None

    # ─────────── 关停 ───────────

    def shutdown(self) -> None:
        """关停所有引擎和 gRPC server，释放所有资源。"""
        with self._lock:
            # 停止 gRPC server
            if self._grpc_server is not None:
                logger.info("stopping shared gRPC server (grace=%ds)...", _GRPC_SHUTDOWN_TIMEOUT)
                try:
                    self._grpc_server.stop(grace=_GRPC_SHUTDOWN_TIMEOUT)
                except Exception as e:
                    logger.warning("gRPC server stop error: %s", e)
                self._grpc_server = None

            # 卸载所有引擎
            for name, slot in self._slots.items():
                if slot.engine is not None:
                    logger.info("unloading engine: %s", name)
                    try:
                        slot.engine.unload()
                    except Exception as e:
                        logger.warning("engine unload error for %s: %s", name, e)
                    slot.engine = None
                    slot.state = ModelState.REGISTERED

            logger.info("all services shutdown complete")

    # ─────────── 兼容旧接口 ───────────

    def ensure_service(self, cfg: ModelDeployConfig) -> RunningService:
        """兼容旧的单模型 ensure_service 接口。

        注册模型配置并立即加载，返回运行信息。
        """
        self.register_model(cfg)
        engine = self.get_or_load_engine(cfg.model_name)
        return RunningService(
            model_name=cfg.model_name,
            engine_type=self._slots[cfg.model_name].engine_type,
            rpc_host=self._grpc_host or cfg.rpc_host,
            rpc_port=self._grpc_port or cfg.rpc_port,
            started_at=self._slots[cfg.model_name].last_accessed,
        )


# ─────────── 全局单例 ───────────

_global_manager: ServiceManager | None = None
_global_lock = threading.Lock()


def get_service_manager() -> ServiceManager:
    """获取全局 ServiceManager 单例。"""
    global _global_manager
    with _global_lock:
        if _global_manager is None:
            _global_manager = ServiceManager()
        return _global_manager
