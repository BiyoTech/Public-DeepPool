"""内存感知守卫 — 多模型并存场景下的内存安全屏障。

职责：
  - 检测系统当前可用内存
  - 判断是否有足够内存加载新模型
  - 配合 ModelRegistry 的 LRU 淘汰策略，在内存不足时触发淘汰

设计原则：
  - 仅提供内存度量和判断能力，不持有任何模型引用
  - 线程安全，可并发调用
"""

from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


def get_available_memory_gb() -> float:
    """获取系统当前可用物理内存（GB）。

    macOS: 通过 vm_stat 计算 free + inactive 页面
    Linux: 通过 /proc/meminfo 读取 MemAvailable
    """
    try:
        if platform.system() == "Darwin":
            return _get_macos_available_memory_gb()
        else:
            return _get_linux_available_memory_gb()
    except Exception:
        logger.warning("failed to detect available memory, assuming 4GB")
        return 4.0


def get_total_memory_gb() -> float:
    """获取系统总物理内存（GB）。"""
    try:
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            return int(result.stdout.strip()) / (1024 ** 3)
        else:
            import os
            mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            return mem_bytes / (1024 ** 3)
    except Exception:
        logger.warning("failed to detect total memory, assuming 16GB")
        return 16.0


def has_enough_memory(reserve_gb: float) -> bool:
    """判断当前可用内存是否满足保留要求。

    Args:
        reserve_gb: 需要为系统保留的最低可用内存（GB）。

    Returns:
        True 表示可用内存充足，可以加载新模型。
    """
    available = get_available_memory_gb()
    enough = available > reserve_gb
    logger.info(
        "memory check: available=%.1fGB reserve=%.1fGB enough=%s",
        available, reserve_gb, enough,
    )
    return enough


# ─────────────────────────────────────────────────
# 平台特定的可用内存检测实现
# ─────────────────────────────────────────────────

def _get_macos_available_memory_gb() -> float:
    """macOS: 通过 vm_stat 获取可用内存。

    可用内存 = (free + inactive) * page_size
    这里用 free + purgeable 作为保守估计，
    因为 macOS 会将 inactive 页面按需回收。
    """
    result = subprocess.run(
        ["vm_stat"], capture_output=True, text=True, timeout=5,
    )
    lines = result.stdout.strip().split("\n")

    page_size = 16384  # Apple Silicon 默认 16KB 页面
    # 首行可能包含 page size 信息
    if "page size of" in lines[0]:
        try:
            page_size = int(lines[0].split("page size of")[1].strip().split()[0])
        except (IndexError, ValueError):
            pass

    stats: dict[str, int] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower()
        # 去掉末尾的句点和空格，提取数字
        val = val.strip().rstrip(".")
        try:
            stats[key] = int(val)
        except ValueError:
            continue

    free_pages = stats.get("pages free", 0)
    # macOS 的 inactive 和 purgeable 页面可被系统按需回收
    inactive_pages = stats.get("pages inactive", 0)
    purgeable_pages = stats.get("pages purgeable", 0)

    # 保守估计：free + purgeable；激进估计会加上 inactive
    available_bytes = (free_pages + inactive_pages + purgeable_pages) * page_size
    return available_bytes / (1024 ** 3)


def _get_linux_available_memory_gb() -> float:
    """Linux: 从 /proc/meminfo 读取 MemAvailable。"""
    with open("/proc/meminfo", "r") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                # 格式: "MemAvailable:   12345678 kB"
                kb = int(line.split()[1])
                return kb / (1024 ** 2)
    # fallback: 使用 free + buffers + cached
    free_kb = 0
    with open("/proc/meminfo", "r") as f:
        for line in f:
            if line.startswith(("MemFree:", "Buffers:", "Cached:")):
                free_kb += int(line.split()[1])
    return free_kb / (1024 ** 2)
