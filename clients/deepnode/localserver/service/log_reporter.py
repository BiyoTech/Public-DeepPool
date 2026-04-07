"""推理日志上报后台任务。

定时从本地 SQLite 查询未上报的推理记录，批量通过 gRPC 上报到平台 Manager，
上报成功后标记为已上报。上报失败仅打日志，不影响推理服务正常运行。
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

# 上报间隔（秒）
_REPORT_INTERVAL = 60
# 单次上报最大条数
_REPORT_BATCH_SIZE = 50


class LogReporter:
    """推理日志上报后台任务。

    Args:
        stats_db: StatisticsDB 实例
        platform_client: PlatformClient 实例
        simei: 设备 SIMEI
    """

    def __init__(self, stats_db, platform_client, simei: str):
        self._stats_db = stats_db
        self._client = platform_client
        self._simei = simei
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """启动上报后台线程。"""
        self._thread = threading.Thread(
            target=self._loop,
            name="log-reporter",
            daemon=True,
        )
        self._thread.start()
        logger.info("LogReporter started simei=%s interval=%ds", self._simei, _REPORT_INTERVAL)

    def stop(self) -> None:
        """停止上报线程。"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
        logger.info("LogReporter stopped")

    def _loop(self) -> None:
        """定时上报循环。"""
        while not self._stop_event.is_set():
            try:
                self._report_once()
            except Exception as exc:
                logger.warning("LogReporter: report failed: %s", exc)

            self._stop_event.wait(timeout=_REPORT_INTERVAL)

    def _report_once(self) -> None:
        """执行一次上报。"""
        records = self._stats_db.get_unreported_records(limit=_REPORT_BATCH_SIZE)
        if not records:
            return

        # 转换为上报格式
        logs = []
        record_ids = []
        for row in records:
            # row: (id, request_id, model_name, prompt_tokens, completion_tokens,
            #        total_tokens, reasoning_tokens, duration_ms, stream, success, created_at,
            #        tool_call_count, tool_call_success, tool_call_retried, tool_call_parse_ms)
            record_ids.append(row[0])
            logs.append({
                "request_id": row[1],
                "model_name": row[2],
                "prompt_tokens": row[3],
                "completion_tokens": row[4],
                "total_tokens": row[5],
                "reasoning_tokens": row[6],
                "duration_ms": row[7],
                "stream": bool(row[8]),
                "success": bool(row[9]),
                "error_message": "",
                "created_at_ms": int(row[10] * 1000),  # unix timestamp -> ms
                "tool_call_count": row[11],
                "tool_call_success": bool(row[12]),
                "tool_call_retried": bool(row[13]),
                "tool_call_parse_ms": row[14],
            })

        accepted = self._client.report_infer_logs(simei=self._simei, logs=logs)
        if accepted > 0:
            self._stats_db.mark_reported(record_ids[:accepted])
            logger.info("LogReporter: reported %d/%d records", accepted, len(records))
