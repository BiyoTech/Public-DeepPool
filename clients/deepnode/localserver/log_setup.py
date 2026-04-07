"""统一日志初始化模块。

同时输出到控制台和文件，文件按天自动滚动，保留指定天数。
日志目录默认 ~/.deeppool/logs/，由 LogConfig 配置驱动。

ERROR 及以上级别日志会通过 TunnelErrorHandler 自动上报到 NodeManager，
无需修改任何业务代码。
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from service.error_log_handler import TunnelErrorHandler

# 统一日志格式
_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 模块级引用，供外部获取 handler 实例以便 bind() NodeManagerClient
_error_handler: TunnelErrorHandler | None = None


def get_error_handler() -> TunnelErrorHandler | None:
    """获取全局 TunnelErrorHandler 实例，用于绑定 NodeManagerClient。"""
    return _error_handler


def setup_logging(
    level: str = "info",
    log_dir: str | Path = "~/.deeppool/logs",
    file_name: str = "localserver.log",
    backup_count: int = 7,
) -> None:
    """初始化全局日志：控制台 + 按天滚动文件 + 错误日志上报三输出。

    Args:
        level:        日志级别（debug / info / warning / error）。
        log_dir:      日志文件目录，支持 ~ 展开。
        file_name:    日志文件名。
        backup_count: 保留历史日志文件天数。
    """
    global _error_handler

    log_dir = Path(log_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / file_name

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # ── 控制台 Handler ──
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    # ── 文件 Handler：按天滚动，午夜切割 ──
    file_handler = TimedRotatingFileHandler(
        filename=str(log_path),
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"  # 历史文件后缀格式：localserver.log.2026-03-24
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)

    # ── 错误日志上报 Handler ──
    from service.error_log_handler import TunnelErrorHandler
    _error_handler = TunnelErrorHandler()
    _error_handler.setFormatter(formatter)

    # ── 配置 root logger ──
    root = logging.getLogger()
    root.setLevel(numeric_level)
    # 清除可能已有的 handler，避免重复
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    root.addHandler(_error_handler)

    # 降低第三方库日志噪音
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "logging initialized: level=%s, file=%s, backup_count=%d, error_report=enabled",
        level, log_path, backup_count,
    )
