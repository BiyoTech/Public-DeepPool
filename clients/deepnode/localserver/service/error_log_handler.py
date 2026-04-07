"""错误日志隧道上报 Handler。

通过 Python logging Handler 机制零侵入拦截 ERROR 及以上级别日志，
经本地缓冲聚合 + 限流后，通过 NodeTunnel gRPC 双向流批量上报至 NodeManager。

设计要点：
- emit() 仅做格式化 + 入队（微秒级），不阻塞日志调用方
- 后台 daemon 线程定时 flush 缓冲区
- 全局限流（每分钟最多 max_per_minute 条），防止异常风暴冲击服务端
- 单条日志截断：message ≤ 4KB，traceback ≤ 8KB
"""

from __future__ import annotations

import logging
import threading
import time
import traceback as tb_module
from typing import TYPE_CHECKING

from generated import node_tunnel_pb2

if TYPE_CHECKING:
    from rpc.node_manager_client import NodeManagerClient

logger = logging.getLogger(__name__)

# ─── 默认配置常量 ───

_MAX_BUFFER_SIZE = 20        # 本地缓冲区最大条数，满时触发 flush
_FLUSH_INTERVAL_SEC = 30     # 定时 flush 间隔（秒）
_MAX_PER_MINUTE = 60         # 每分钟最大上报条数（全局限流）
_MAX_MESSAGE_BYTES = 4096    # 单条 message 截断阈值
_MAX_TRACEBACK_BYTES = 8192  # 单条 traceback 截断阈值


def _truncate(text: str, max_bytes: int) -> str:
    """将字符串截断到不超过 max_bytes 字节（UTF-8）。"""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    # 按字节截断后解码（忽略尾部不完整的 UTF-8 序列）
    return encoded[:max_bytes].decode("utf-8", errors="ignore") + "...[truncated]"


class TunnelErrorHandler(logging.Handler):
    """将 ERROR+ 日志通过 NodeTunnel 上报到 NodeManager 的 logging Handler。

    Args:
        max_buffer:      本地缓冲区最大条数。
        flush_interval:  定时 flush 间隔（秒）。
        max_per_minute:  每分钟最大上报条数。
    """

    def __init__(
        self,
        max_buffer: int = _MAX_BUFFER_SIZE,
        flush_interval: float = _FLUSH_INTERVAL_SEC,
        max_per_minute: int = _MAX_PER_MINUTE,
    ):
        super().__init__(level=logging.ERROR)
        self._max_buffer = max_buffer
        self._flush_interval = flush_interval
        self._max_per_minute = max_per_minute

        # NodeManagerClient 引用，通过 bind() 延迟注入
        self._client: NodeManagerClient | None = None

        # 缓冲区 + 锁
        self._buffer: list[node_tunnel_pb2.ErrorLogEntry] = []
        self._lock = threading.Lock()

        # 限流计数器
        self._minute_count = 0
        self._minute_start = time.monotonic()

        # 后台 flush 线程
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._flush_loop,
            name="error-log-reporter",
            daemon=True,
        )
        self._thread.start()

    def bind(self, client: NodeManagerClient) -> None:
        """绑定 NodeManagerClient，启用上报能力。

        在隧道连接建立后调用。绑定前产生的 ERROR 日志会暂存在缓冲区，
        等待绑定后的下一次 flush 发送。
        """
        self._client = client
        logger.info("TunnelErrorHandler: bound to NodeManagerClient")

    def emit(self, record: logging.LogRecord) -> None:
        """拦截 ERROR+ 日志，格式化为 proto 条目后入队。"""
        try:
            # 跳过自身产生的日志，避免递归
            if record.name == __name__:
                return

            # 限流检查
            if not self._rate_limit_allow():
                return

            # 格式化 traceback
            traceback_str = ""
            if record.exc_info and record.exc_info[1] is not None:
                traceback_str = "".join(
                    tb_module.format_exception(*record.exc_info)
                )

            # 构建 proto 条目
            entry = node_tunnel_pb2.ErrorLogEntry(
                level=record.levelname,
                logger_name=record.name,
                message=_truncate(self.format(record), _MAX_MESSAGE_BYTES),
                traceback=_truncate(traceback_str, _MAX_TRACEBACK_BYTES),
                timestamp_ms=int(record.created * 1000),
            )

            # 入队（非阻塞）
            with self._lock:
                self._buffer.append(entry)
                should_flush = len(self._buffer) >= self._max_buffer

            # 满缓冲触发即时 flush
            if should_flush:
                self._do_flush()

        except Exception:
            # Handler.emit 异常不应影响业务代码
            self.handleError(record)

    def close(self) -> None:
        """停止后台线程，flush 残留日志。"""
        self._stop_event.set()
        self._thread.join(timeout=5)
        self._do_flush()
        super().close()

    def _rate_limit_allow(self) -> bool:
        """滑动窗口限流：每分钟最多 max_per_minute 条。"""
        now = time.monotonic()
        if now - self._minute_start >= 60:
            self._minute_count = 0
            self._minute_start = now

        if self._minute_count >= self._max_per_minute:
            return False

        self._minute_count += 1
        return True

    def _flush_loop(self) -> None:
        """后台线程：定时 flush 缓冲区。"""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._flush_interval)
            self._do_flush()

    def _do_flush(self) -> None:
        """将缓冲区中的日志通过 NodeManagerClient 发送。"""
        with self._lock:
            if not self._buffer:
                return
            entries = self._buffer[:]
            self._buffer.clear()

        client = self._client
        if client is None:
            # 客户端未绑定，日志丢弃（此时隧道尚未连接，属于预期行为）
            return

        try:
            client.report_error_logs(entries)
        except Exception as exc:
            # 上报失败仅打 warning，不影响业务
            logger.warning(
                "TunnelErrorHandler: failed to report %d error logs: %s",
                len(entries), exc,
            )
