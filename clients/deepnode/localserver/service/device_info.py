"""设备静态硬件信息采集模块。

采集维度（跨平台 macOS / Linux / Windows）：
  - 设备型号（如 MacBook Pro, Dell PowerEdge R750）
  - CPU 核数（物理核 + 逻辑核）
  - GPU 型号与核数
  - 总内存（GB）
  - 磁盘总空间与可用空间（GB）
  - 操作系统名称与版本

设计原则：
  - 所有采集函数失败时静默降级，返回合理默认值
  - 采集结果缓存，整个进程生命周期只采集一次
  - 仅提供只读数据，无副作用
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import threading
from dataclasses import dataclass, field, asdict

import psutil

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceHardwareInfo:
    """设备静态硬件信息快照。"""

    device_model: str = ""           # 设备型号，如 "MacBook Pro" / "Dell PowerEdge R750"
    os_name: str = ""                # 操作系统名称，如 "macOS" / "Linux" / "Windows"
    os_version: str = ""             # 操作系统版本
    cpu_brand: str = ""              # CPU 品牌型号
    cpu_physical_cores: int = 0      # CPU 物理核数
    cpu_logical_cores: int = 0       # CPU 逻辑核数（含超线程）
    gpu_name: str = ""               # GPU 型号
    gpu_cores: int = 0               # GPU 核心数（Apple Silicon 为 GPU 核心数，NVIDIA 为 CUDA 核心数）
    total_memory_gb: float = 0.0     # 系统总内存（GB）
    disk_total_gb: float = 0.0       # 磁盘总空间（GB）
    disk_available_gb: float = 0.0   # 磁盘可用空间（GB）

    def to_dict(self) -> dict:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)


# ─────────────────────────────────────────────────
# 跨平台采集函数
# ─────────────────────────────────────────────────

def _run_cmd(cmd: list[str], timeout: int = 10) -> str:
    """安全执行系统命令，失败返回空字符串。"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _collect_device_model() -> str:
    """获取设备型号。"""
    system = platform.system()
    try:
        if system == "Darwin":
            # macOS: system_profiler 获取 Model Name
            output = _run_cmd(["system_profiler", "SPHardwareDataType"])
            for line in output.splitlines():
                stripped = line.strip()
                if stripped.startswith("Model Name:"):
                    return stripped.split(":", 1)[1].strip()
        elif system == "Linux":
            # Linux: DMI product name
            name = _run_cmd(["cat", "/sys/class/dmi/id/product_name"])
            if name and name.lower() not in ("", "none", "n/a", "system product name"):
                return name
        elif system == "Windows":
            output = _run_cmd(["powershell", "-NoProfile", "-Command",
                               "(Get-CimInstance Win32_ComputerSystem).Model"])
            if output:
                return output
    except Exception as exc:
        logger.debug("failed to collect device model: %s", exc)
    return ""


def _collect_cpu_info() -> tuple[str, int, int]:
    """获取 CPU 品牌、物理核数、逻辑核数。"""
    brand = ""
    physical = psutil.cpu_count(logical=False) or 0
    logical = psutil.cpu_count(logical=True) or os.cpu_count() or 0

    system = platform.system()
    try:
        if system == "Darwin":
            brand = _run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])
        elif system == "Linux":
            output = _run_cmd(["cat", "/proc/cpuinfo"])
            for line in output.splitlines():
                if line.strip().lower().startswith("model name"):
                    brand = line.split(":", 1)[1].strip() if ":" in line else ""
                    break
        elif system == "Windows":
            brand = _run_cmd(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"])
    except Exception as exc:
        logger.debug("failed to collect CPU brand: %s", exc)

    return brand, physical, logical


def _collect_gpu_info() -> tuple[str, int]:
    """获取 GPU 型号和核心数。

    macOS Apple Silicon: 通过 system_profiler 获取 GPU 核心数
    Linux NVIDIA: 通过 nvidia-smi 获取型号和 CUDA 核心数
    """
    gpu_name = ""
    gpu_cores = 0
    system = platform.system()

    try:
        if system == "Darwin":
            # 获取 GPU 型号
            output = _run_cmd(["system_profiler", "SPDisplaysDataType", "-detailLevel", "basic"])
            for line in output.splitlines():
                stripped = line.strip()
                if stripped.startswith("Chipset Model:") or stripped.startswith("Chip:"):
                    gpu_name = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("Total Number of Cores:"):
                    try:
                        gpu_cores = int(stripped.split(":", 1)[1].strip())
                    except ValueError:
                        pass
        elif system == "Linux":
            # nvidia-smi 获取 GPU 名称
            output = _run_cmd(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"])
            if output:
                gpu_name = output.splitlines()[0].strip()
            # CUDA 核心数需要通过 nvidia-smi 查询
            cores_output = _run_cmd(["nvidia-smi", "--query-gpu=driver_version",
                                     "--format=csv,noheader,nounits"])
            # nvidia-smi 无法直接查询 CUDA 核心数，尝试 deviceQuery
            cuda_output = _run_cmd(["nvidia-smi", "-q", "-d", "COMPUTE"])
            for line in cuda_output.splitlines():
                stripped = line.strip()
                if "CUDA Cores" in stripped:
                    try:
                        gpu_cores = int(stripped.split(":")[-1].strip())
                    except ValueError:
                        pass
        elif system == "Windows":
            gpu_name = _run_cmd(["powershell", "-NoProfile", "-Command",
                                 "(Get-CimInstance Win32_VideoController | Select-Object -First 1).Name"])
    except Exception as exc:
        logger.debug("failed to collect GPU info: %s", exc)

    return gpu_name, gpu_cores


def _collect_memory_gb() -> float:
    """获取系统总物理内存（GB）。"""
    try:
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        logger.debug("failed to collect total memory via psutil, fallback to platform-specific")
    # fallback
    try:
        if platform.system() == "Darwin":
            output = _run_cmd(["sysctl", "-n", "hw.memsize"])
            return int(output) / (1024 ** 3) if output else 0.0
        else:
            mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            return mem_bytes / (1024 ** 3)
    except Exception:
        return 0.0


def _collect_disk_info() -> tuple[float, float]:
    """获取根分区磁盘总空间和可用空间（GB）。"""
    try:
        usage = shutil.disk_usage("/")
        total_gb = round(usage.total / (1024 ** 3), 1)
        free_gb = round(usage.free / (1024 ** 3), 1)
        return total_gb, free_gb
    except Exception as exc:
        logger.debug("failed to collect disk info: %s", exc)
        return 0.0, 0.0


def _collect_os_info() -> tuple[str, str]:
    """获取操作系统名称和版本。"""
    system = platform.system()
    if system == "Darwin":
        version = platform.mac_ver()[0] or platform.release()
        return "macOS", version
    elif system == "Linux":
        # 尝试读取发行版信息
        try:
            import distro  # type: ignore
            return distro.name() or "Linux", distro.version() or platform.release()
        except ImportError:
            return "Linux", platform.release()
    elif system == "Windows":
        return "Windows", platform.version()
    return system, platform.release()


# ─────────────────────────────────────────────────
# 主采集入口 + 缓存
# ─────────────────────────────────────────────────

def collect_device_hardware_info() -> DeviceHardwareInfo:
    """采集设备静态硬件信息。

    所有子项采集失败时返回默认空值，不会抛出异常。
    """
    device_model = _collect_device_model()
    cpu_brand, cpu_physical, cpu_logical = _collect_cpu_info()
    gpu_name, gpu_cores = _collect_gpu_info()
    total_memory = _collect_memory_gb()
    disk_total, disk_available = _collect_disk_info()
    os_name, os_version = _collect_os_info()

    info = DeviceHardwareInfo(
        device_model=device_model,
        os_name=os_name,
        os_version=os_version,
        cpu_brand=cpu_brand,
        cpu_physical_cores=cpu_physical,
        cpu_logical_cores=cpu_logical,
        gpu_name=gpu_name,
        gpu_cores=gpu_cores,
        total_memory_gb=round(total_memory, 1),
        disk_total_gb=disk_total,
        disk_available_gb=disk_available,
    )

    logger.info(
        "device hardware info collected: model=%s cpu=%d/%d gpu=%s(%d cores) "
        "memory=%.1fGB disk=%.1f/%.1fGB os=%s %s",
        info.device_model, info.cpu_physical_cores, info.cpu_logical_cores,
        info.gpu_name, info.gpu_cores, info.total_memory_gb,
        info.disk_available_gb, info.disk_total_gb, info.os_name, info.os_version,
    )
    return info


# 缓存：进程生命周期内只采集一次
_cached_info: DeviceHardwareInfo | None = None
_cache_lock = threading.Lock()


def get_device_hardware_info() -> DeviceHardwareInfo:
    """获取设备硬件信息（带缓存），首次调用时采集，后续直接返回。"""
    global _cached_info
    if _cached_info is not None:
        return _cached_info

    with _cache_lock:
        if _cached_info is not None:
            return _cached_info
        _cached_info = collect_device_hardware_info()
        return _cached_info
