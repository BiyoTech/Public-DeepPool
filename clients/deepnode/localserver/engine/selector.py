"""推理引擎自动选择 — 根据当前系统平台和硬件自动决定最优引擎。

选择策略：
  1. macOS + Apple Silicon (M系列) + macOS >= 13.5  → vllm-mlx
  2. macOS + Intel 芯片 或 macOS < 13.5             → llama.cpp
  3. Linux                                           → vLLM
  4. Windows                                         → 不支持，抛出异常
"""

from __future__ import annotations

import logging
import platform
import re
import subprocess

logger = logging.getLogger(__name__)


def detect_engine_type() -> str:
    """检测当前系统环境，返回推荐的引擎类型标识。

    Returns:
        "vllm_mlx"  — Mac M系列 + macOS >= 13.5
        "llamacpp"  — Mac Intel 或 macOS < 13.5
        "vllm"      — Linux

    Raises:
        RuntimeError: Windows 或其他不支持的系统
    """
    system = platform.system()

    if system == "Darwin":
        engine = _select_macos_engine()
        logger.info(
            "platform detected: macOS, chip=%s, version=%s, selected engine=%s",
            platform.machine(), platform.mac_ver()[0], engine,
        )
        return engine

    if system == "Linux":
        logger.info("platform detected: Linux, selected engine=vllm")
        return "vllm"

    raise RuntimeError(
        f"unsupported platform: {system}. "
        "Currently only macOS and Linux are supported."
    )


def _select_macos_engine() -> str:
    """macOS 下根据芯片类型和系统版本选择引擎。"""
    is_apple_silicon = _is_apple_silicon()
    macos_version = _parse_macos_version()

    if is_apple_silicon and macos_version >= (13, 5):
        return "vllm_mlx"

    return "llamacpp"


def _is_apple_silicon() -> bool:
    """判断当前 Mac 是否为 Apple Silicon (M系列芯片)。"""
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return True

    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=5,
        )
        brand = result.stdout.strip().lower()
        return "apple" in brand
    except Exception:
        return False


def _parse_macos_version() -> tuple[int, ...]:
    """解析 macOS 版本号，返回 (major, minor, ...) 元组。"""
    ver_str = platform.mac_ver()[0]
    if not ver_str:
        try:
            result = subprocess.run(
                ["sw_vers", "-productVersion"],
                capture_output=True, text=True, timeout=5,
            )
            ver_str = result.stdout.strip()
        except Exception:
            logger.warning("failed to detect macOS version, assuming 0.0")
            return (0, 0)

    parts = re.findall(r"\d+", ver_str)
    if not parts:
        return (0, 0)
    return tuple(int(p) for p in parts)
