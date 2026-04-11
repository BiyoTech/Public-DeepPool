"""推理统计 API — 供前端设备详情页查询。"""

from __future__ import annotations

import logging
import platform
import re
import subprocess
import psutil

from fastapi import APIRouter

from service.manager import get_service_manager
from service.statistics import get_statistics_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["stats"])

# ---------------------------------------------------------------------------
# GPU 信息采集（跨平台）
#
# macOS (Apple Silicon / Intel):
#   通过 ioreg 读取 IOAccelerator 的 PerformanceStatistics，无需 sudo。
#   - "Device Utilization %" — GPU 整体利用率
#   - "Renderer Utilization %" / "Tiler Utilization %" — 可选细项
#   GPU 型号通过 system_profiler 获取。
#
# Linux (NVIDIA):
#   通过 nvidia-smi 读取 GPU 名称、利用率、温度。
# ---------------------------------------------------------------------------


def _get_gpu_info_darwin() -> dict:
    """macOS: 读取真实 GPU 利用率与型号（兼容 Apple Silicon 和 Intel Mac）。"""
    gpu_info: dict = {"gpu_name": "", "gpu_load_percent": 0.0, "gpu_temp_celsius": 0.0}

    # 1) 通过 ioreg 读取 GPU 利用率（无需 sudo）
    try:
        result = subprocess.run(
            ["ioreg", "-r", "-l", "-w0", "-c", "IOAccelerator"],
            capture_output=True, text=True, timeout=5,
        )
        # 匹配形如 "Device Utilization %" = 37
        match = re.search(r'"Device Utilization %"\s*=\s*(\d+)', result.stdout)
        if match:
            gpu_info["gpu_load_percent"] = float(match.group(1))
            logger.debug("ioreg GPU utilization: %s%%", match.group(1))
    except Exception as e:
        logger.warning("Failed to read GPU utilization via ioreg: %s", e)

    # 2) 通过 system_profiler 获取 GPU 型号（开销较大，但仅取名字）
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-detailLevel", "basic"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            stripped = line.strip()
            # Apple Silicon: "Chipset Model: Apple M4 Pro"；Intel: "Chipset Model: Intel Iris Plus ..."
            if stripped.startswith("Chipset Model:") or stripped.startswith("Chip:"):
                gpu_info["gpu_name"] = stripped.split(":", 1)[1].strip()
                break
    except Exception as e:
        logger.warning("Failed to read GPU name via system_profiler: %s", e)

    return gpu_info


def _get_gpu_info_linux() -> dict:
    """Linux: 通过 nvidia-smi 读取 NVIDIA GPU 利用率、型号、温度。"""
    gpu_info: dict = {"gpu_name": "", "gpu_load_percent": 0.0, "gpu_temp_celsius": 0.0}

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        parts = result.stdout.strip().split(",")
        if len(parts) >= 3:
            gpu_info["gpu_name"] = parts[0].strip()
            gpu_info["gpu_load_percent"] = float(parts[1].strip())
            gpu_info["gpu_temp_celsius"] = float(parts[2].strip())
    except Exception as e:
        logger.warning("Failed to read GPU info via nvidia-smi: %s", e)

    return gpu_info


def _get_hardware_info() -> dict:
    """采集当前设备硬件信息（CPU 负载、内存、GPU 利用率等）。"""
    info: dict = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "gpu_name": "",
        "gpu_load_percent": 0.0,
        "gpu_temp_celsius": 0.0,
    }

    system = platform.system()
    if system == "Darwin":
        gpu = _get_gpu_info_darwin()
    else:
        gpu = _get_gpu_info_linux()

    info.update(gpu)
    return info


@router.get("/snapshot")
def get_stats_snapshot() -> dict:
    """Return inference stats snapshot + hardware info + service status + device status."""
    from api.init import get_device_status

    stats_db = get_statistics_db()
    snapshot = stats_db.get_snapshot(recent_seconds=60)

    manager = get_service_manager()
    running = manager.get_running_service()

    hardware = _get_hardware_info()

    return {
        "code": 0,
        "message": "ok",
        "data": {
            # Service status
            "service": {
                "running": running is not None,
                "model_name": running.model_name if running else "",
                "engine_type": running.engine_type if running else "",
                "uptime_seconds": int(__import__("time").time() - running.started_at) if running else 0,
            },
            # Device security status from platform ("active" / "blocked" / "cheating")
            "device_status": get_device_status(),
            # 硬件信息
            "hardware": hardware,
            # 全量统计
            "total": {
                "requests": snapshot.total_requests,
                "prompt_tokens": snapshot.total_prompt_tokens,
                "completion_tokens": snapshot.total_completion_tokens,
                "total_tokens": snapshot.total_tokens,
                "reasoning_tokens": snapshot.total_reasoning_tokens,
                "avg_duration_ms": snapshot.avg_duration_ms,
                "local_requests": snapshot.local_requests,
                "tunnel_requests": snapshot.tunnel_requests,
            },
            # 今日统计
            "today": {
                "requests": snapshot.today_requests,
                "prompt_tokens": snapshot.today_prompt_tokens,
                "completion_tokens": snapshot.today_completion_tokens,
                "total_tokens": snapshot.today_total_tokens,
            },
            # 最近 60 秒统计（用于计算速率）
            "recent_60s": {
                "requests": snapshot.recent_requests,
                "prompt_tokens": snapshot.recent_prompt_tokens,
                "completion_tokens": snapshot.recent_completion_tokens,
                "token_output_rate": snapshot.token_output_rate,
            },
        },
    }
