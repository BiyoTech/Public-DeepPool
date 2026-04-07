"""localserver 配置加载模块。

从 config.yaml 加载配置，支持环境变量 LOCALSERVER_CONFIG 指定配置文件路径。
未显式指定的 engine 参数会根据当前系统硬件自动推荐默认值。
"""

from __future__ import annotations

import logging
import os
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent
_DEFAULT_CONFIG_PATH = _CONFIG_DIR / "config.yaml"


@dataclass
class ServerConfig:
    """本地 HTTP 服务配置。"""
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class PlatformConfig:
    """Platform 各组件 gRPC 地址配置。"""
    manager_grpc_target: str = "127.0.0.1:9090"
    scheduler_grpc_target: str = "127.0.0.1:9091"
    nodemanager_grpc_target: str = "127.0.0.1:9092"
    grpc_tls: bool = False                  # 是否启用 gRPC TLS 加密连接
    grpc_tls_ca_cert: str = ""              # CA 证书路径（PEM）；留空则使用系统根证书


@dataclass
class LogConfig:
    """日志配置。

    Attributes:
        level:        日志级别（debug / info / warning / error）。
        log_dir:      日志文件落盘目录，支持 ~ 展开。
        file_name:    日志文件名。
        backup_count: 按天滚动时保留的历史日志文件天数。
    """
    level: str = "info"
    log_dir: str = "~/.deeppool/logs"
    file_name: str = "localserver.log"
    backup_count: int = 7


@dataclass
class EngineConfig:
    """Inference engine performance configuration.

    All fields can be explicitly set in config.yaml; unset values (0/False)
    are auto-filled by auto_fill_defaults() based on system hardware.

    Parameters:
      - use_paged_cache:       Enable paged KV Cache (MLX → RotatingKVCache)
      - max_kv_size:           Max KV Cache entries (0 = auto)
      - kv_bits:               KV Cache quantization bits (0 = no quantization)
      - kv_group_size:         KV Cache quantization group size
      - continuous_batching:   Enable continuous batching (reserved; MLX single-request serial)
      - num_workers:           gRPC server thread pool size
      - tokenizer_workers:     Tokenizer encode/decode CPU thread pool size
      - tokenizer_prefer_cpu:  Force tokenizer ops on CPU (avoid GPU contention)
      - cpu_offload_fraction:  CPU offload ratio 0.0~1.0 (reserved)
      - prefill_step_size:     Base prefill step size — the engine dynamically adapts this
                               per-request based on prompt length and available memory.
                               Short prompts skip chunked prefill entirely.
      - tool_call_strategy:    FC parsing strategy (vllm_mlx only)
      - tool_call_temperature: FC scenario temperature cap
      - tool_call_max_tokens:  FC scenario max_tokens cap
    """
    use_paged_cache: bool = False
    max_kv_size: int = 0
    kv_bits: int = 0
    kv_group_size: int = 64
    continuous_batching: bool = False
    num_workers: int = 0         # 0 = 自动推荐
    tokenizer_workers: int = 0   # 0 = 自动推荐
    tokenizer_prefer_cpu: bool = True
    cpu_offload_fraction: float = 0.0
    prefill_step_size: int = 0   # 0 = 自动推荐
    # --- Function Call 配置 ---
    tool_call_strategy: str = "auto"        # parser_only / outlines_only / parser_fallback_outlines / auto
    tool_call_temperature: float = 0.2      # FC 场景温度上限（tools 非空时 temperature 不超过此值）
    tool_call_max_tokens: int = 512         # FC 场景 max_tokens 上限

    def auto_fill_defaults(self, engine_type: str = "") -> None:
        """根据系统硬件和引擎类型自动填充未指定（值为 0 / False）的配置项。

        Args:
            engine_type: 引擎类型标识（vllm_mlx / vllm / llamacpp），
                         用于按平台差异化推荐默认值。为空时按通用策略推荐。
        """
        cpu_count = os.cpu_count() or 4
        total_mem_gb = _get_system_memory_gb()
        engine_type = engine_type.strip().lower()

        # --- num_workers: gRPC 并发线程数 ---
        if self.num_workers <= 0:
            if engine_type == "llamacpp":
                # llama.cpp 引擎较轻量，线程池无需过大
                self.num_workers = max(2, min(cpu_count, 4))
            else:
                self.num_workers = max(2, min(cpu_count, 8))

        # --- tokenizer_workers: 编码/解码专用 CPU 线程池 ---
        if self.tokenizer_workers <= 0:
            if engine_type == "llamacpp":
                # llama.cpp 内部管理 tokenizer，无需外部线程池
                self.tokenizer_workers = 0
            else:
                self.tokenizer_workers = max(2, cpu_count // 2)

        # --- prefill_step_size: chunked prompt encoding to prevent peak memory OOM ---
        # The actual step used per-request is dynamically adapted by the engine
        # based on prompt length and available memory. This value serves as the
        # base/maximum step size for the adaptive algorithm.
        if self.prefill_step_size <= 0:
            if engine_type == "vllm_mlx":
                # MLX Metal unified memory: scale base step by total memory
                if total_mem_gb >= 64:
                    self.prefill_step_size = 2048
                elif total_mem_gb >= 32:
                    self.prefill_step_size = 1536
                else:
                    self.prefill_step_size = 768
            else:
                # vLLM / llama.cpp manage prefill internally
                self.prefill_step_size = 512

        # --- max_kv_size: 根据可用内存自动推荐 ---
        if self.max_kv_size <= 0:
            if total_mem_gb >= 64:
                self.max_kv_size = 16384
            elif total_mem_gb >= 32:
                self.max_kv_size = 8192
            else:
                self.max_kv_size = 4096

        # --- continuous_batching: MLX Metal 有线程安全问题，强制关闭 ---
        if engine_type == "vllm_mlx":
            self.continuous_batching = False

        # --- tool_call_strategy: "auto" → 根据 outlinesmlx 可用性解析为具体策略 ---
        if self.tool_call_strategy == "auto":
            if engine_type == "vllm_mlx":
                try:
                    import outlines  # noqa: F401 — 仅检测可用性
                    self.tool_call_strategy = "parser_fallback_outlines"
                except ImportError:
                    self.tool_call_strategy = "parser_only"
            else:
                # 非 MLX 引擎不使用 outlines-mlx
                self.tool_call_strategy = "parser_only"

        logger.info(
            "engine config (auto-filled, engine=%s): num_workers=%d tokenizer_workers=%d "
            "prefill_step_size=%d max_kv_size=%d kv_bits=%d "
            "tokenizer_prefer_cpu=%s use_paged_cache=%s continuous_batching=%s "
            "tool_call_strategy=%s tool_call_temperature=%.2f tool_call_max_tokens=%d",
            engine_type or "unknown",
            self.num_workers, self.tokenizer_workers,
            self.prefill_step_size, self.max_kv_size, self.kv_bits,
            self.tokenizer_prefer_cpu, self.use_paged_cache,
            self.continuous_batching,
            self.tool_call_strategy, self.tool_call_temperature,
            self.tool_call_max_tokens,
        )

    def to_dict(self) -> dict[str, Any]:
        """导出为可序列化字典，用于 device_config 上报。"""
        return asdict(self)


def _get_system_memory_gb() -> float:
    """获取系统物理内存（GB），用于自动推荐配置默认值。"""
    try:
        if platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            return int(result.stdout.strip()) / (1024 ** 3)
        else:
            mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            return mem_bytes / (1024 ** 3)
    except Exception:
        logger.warning("failed to detect system memory, assuming 16GB")
        return 16.0


@dataclass
class MultiModelConfig:
    """多模型管理配置。

    Attributes:
        max_loaded_models:  同时加载到内存的最大模型数量（0 表示不限制，仅靠内存守卫管理）。
        memory_reserve_gb:  为系统保留的最低可用内存（GB），
                            加载新模型前若可用内存低于此值，触发 LRU 淘汰。
    """
    max_loaded_models: int = 3
    memory_reserve_gb: float = 4.0


@dataclass
class StandaloneConfig:
    """独立运行模式配置。

    启用后 localserver 自动生成 simei 并完成设备初始化，
    无需 Tauri 桌面应用，用户通过浏览器访问状态页。

    Attributes:
        enabled:  是否启用独立运行模式。
        token:    platform 认证 token（与 account/password 二选一）。
        account:  platform 登录账号（与 token 二选一，配合 password 使用）。
        password: platform 登录密码。
    """
    enabled: bool = False
    token: str = ""
    account: str = ""
    password: str = ""


@dataclass
class AppConfig:
    """localserver 全局配置。"""
    server: ServerConfig = field(default_factory=ServerConfig)
    platform: PlatformConfig = field(default_factory=PlatformConfig)
    log: LogConfig = field(default_factory=LogConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    multi_model: MultiModelConfig = field(default_factory=MultiModelConfig)
    standalone: StandaloneConfig = field(default_factory=StandaloneConfig)


def _build_config(raw: dict[str, Any]) -> AppConfig:
    """从原始 dict 构建 AppConfig，缺失字段用默认值。"""
    server_raw = raw.get("server") or {}
    platform_raw = raw.get("platform") or {}
    log_raw = raw.get("log") or {}
    engine_raw = raw.get("engine") or {}
    multi_model_raw = raw.get("multi_model") or {}
    standalone_raw = raw.get("standalone") or {}

    engine_cfg = EngineConfig(
        use_paged_cache=bool(engine_raw.get("use_paged_cache", False)),
        max_kv_size=int(engine_raw.get("max_kv_size", 0)),
        kv_bits=int(engine_raw.get("kv_bits", 0)),
        kv_group_size=int(engine_raw.get("kv_group_size", 64)),
        continuous_batching=bool(engine_raw.get("continuous_batching", False)),
        num_workers=int(engine_raw.get("num_workers", 0)),
        tokenizer_workers=int(engine_raw.get("tokenizer_workers", 0)),
        tokenizer_prefer_cpu=bool(engine_raw.get("tokenizer_prefer_cpu", True)),
        cpu_offload_fraction=float(engine_raw.get("cpu_offload_fraction", 0.0)),
        prefill_step_size=int(engine_raw.get("prefill_step_size", 0)),
        tool_call_strategy=str(engine_raw.get("tool_call_strategy", "auto")),
        tool_call_temperature=float(engine_raw.get("tool_call_temperature", 0.2)),
        tool_call_max_tokens=int(engine_raw.get("tool_call_max_tokens", 512)),
    )
    # 注意：auto_fill_defaults 需要 engine_type 参数做差异化推荐，
    # 因此延迟到 ServiceManager._create_engine 确定引擎类型后再调用。
    # 这里只做 YAML → dataclass 的字段映射。

    return AppConfig(
        server=ServerConfig(
            host=str(server_raw.get("host", "127.0.0.1")),
            port=int(server_raw.get("port", 8765)),
        ),
        platform=PlatformConfig(
            manager_grpc_target=str(platform_raw.get("manager_grpc_target", "127.0.0.1:9090")),
            scheduler_grpc_target=str(platform_raw.get("scheduler_grpc_target", "127.0.0.1:9091")),
            nodemanager_grpc_target=str(platform_raw.get("nodemanager_grpc_target", "127.0.0.1:9092")),
            grpc_tls=bool(platform_raw.get("grpc_tls", False)),
            grpc_tls_ca_cert=str(platform_raw.get("grpc_tls_ca_cert", "")),
        ),
        log=LogConfig(
            level=str(log_raw.get("level", "info")).lower(),
            log_dir=str(log_raw.get("log_dir", "~/.deeppool/logs")),
            file_name=str(log_raw.get("file_name", "localserver.log")),
            backup_count=int(log_raw.get("backup_count", 7)),
        ),
        engine=engine_cfg,
        multi_model=MultiModelConfig(
            max_loaded_models=int(multi_model_raw.get("max_loaded_models", 3)),
            memory_reserve_gb=float(multi_model_raw.get("memory_reserve_gb", 4.0)),
        ),
        standalone=StandaloneConfig(
            enabled=bool(standalone_raw.get("enabled", False)),
            token=str(standalone_raw.get("token", "")),
            account=str(standalone_raw.get("account", "")),
            password=str(standalone_raw.get("password", "")),
        ),
    )


def load_config(path: str | Path | None = None) -> AppConfig:
    """加载配置文件。

    优先级：参数 path > 环境变量 LOCALSERVER_CONFIG > 默认 config.yaml
    """
    if path is None:
        path = os.environ.get("LOCALSERVER_CONFIG", "").strip() or _DEFAULT_CONFIG_PATH
    path = Path(path)

    if not path.exists():
        logger.warning("config file not found: %s, using defaults", path)
        return AppConfig()

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = _build_config(raw)
    logger.info("config loaded from %s", path)
    return cfg


# 模块级单例，启动时初始化一次
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """获取全局配置单例。首次调用自动加载。"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def init_config(path: str | Path | None = None) -> AppConfig:
    """显式初始化全局配置（供 main.py 启动时调用）。"""
    global _config
    _config = load_config(path)
    return _config
