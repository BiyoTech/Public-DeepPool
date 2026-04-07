"""推理统计模块 — 基于 SQLite 的本地持久化统计。

使用 SQLite 记录每次推理请求的关键指标（token 用量、耗时等），
并提供聚合查询接口供前端展示。

数据库文件存储在 ~/.deeppool/statistics/stats.db。
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# 数据库存储目录
_DB_DIR = Path.home() / ".deeppool" / "statistics"
_DB_PATH = _DB_DIR / "stats.db"

# 建表 DDL（新表直接包含 reported 列）
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS infer_requests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id    TEXT    NOT NULL,
    source        TEXT    NOT NULL DEFAULT 'local',  -- 'local'(gRPC直连) / 'tunnel'(nodemanager下发)
    model_name    TEXT    NOT NULL DEFAULT '',
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    reasoning_tokens  INTEGER NOT NULL DEFAULT 0,
    duration_ms       INTEGER NOT NULL DEFAULT 0,    -- 推理总耗时(ms)
    stream            INTEGER NOT NULL DEFAULT 0,    -- 是否流式(0/1)
    success           INTEGER NOT NULL DEFAULT 1,    -- 是否成功(0/1)
    created_at        REAL    NOT NULL,              -- unix timestamp
    reported          INTEGER NOT NULL DEFAULT 0     -- 是否已上报到平台(0/1)
);

CREATE INDEX IF NOT EXISTS idx_infer_created_at ON infer_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_infer_source ON infer_requests(source);
"""

# reported 列的索引需要在迁移完成后再创建（旧表在 executescript 时尚无该列）
_CREATE_REPORTED_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_infer_reported ON infer_requests(reported);
"""

# 迁移语句：为旧表添加 reported 列
_MIGRATE_REPORTED_COLUMN = """
ALTER TABLE infer_requests ADD COLUMN reported INTEGER NOT NULL DEFAULT 0;
"""


@dataclass
class InferRecord:
    """单次推理请求记录。"""
    request_id: str
    source: str            # "local" / "tunnel"
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    duration_ms: int = 0
    stream: bool = False
    success: bool = True
    # Function Call 指标
    tool_call_count: int = 0
    tool_call_success: bool = True
    tool_call_retried: bool = False
    tool_call_parse_ms: int = 0


@dataclass
class StatsSnapshot:
    """聚合统计快照，供前端展示。"""
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_reasoning_tokens: int = 0
    avg_duration_ms: float = 0.0
    # 按来源分类
    local_requests: int = 0
    tunnel_requests: int = 0
    # 最近一段时间（如最近 60 秒）的速率统计
    recent_requests: int = 0
    recent_prompt_tokens: int = 0
    recent_completion_tokens: int = 0
    # Token output throughput (tokens/sec), calculated from recent window.
    # Accounts for concurrent requests: sum of all completion_tokens / wall-clock seconds.
    token_output_rate: float = 0.0
    # 今日统计
    today_requests: int = 0
    today_prompt_tokens: int = 0
    today_completion_tokens: int = 0
    today_total_tokens: int = 0


class StatisticsDB:
    """线程安全的统计数据库操作封装。"""

    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库：创建目录、建表、迁移旧表、创建索引。"""
        os.makedirs(self._db_path.parent, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        # 建表 + 基础索引（不含 reported 索引，因为旧表可能尚无该列）
        self._conn.executescript(_CREATE_TABLE_SQL)
        self._conn.commit()
        # 迁移：为旧表添加 reported 列（幂等）
        self._migrate_reported_column()
        # 迁移：为旧表添加 tool_call 列（幂等）
        self._migrate_tool_call_columns()
        # reported 列确保存在后再创建其索引
        self._conn.executescript(_CREATE_REPORTED_INDEX_SQL)
        self._conn.commit()
        logger.info("statistics db initialized path=%s", self._db_path)

    def _migrate_reported_column(self) -> None:
        """为已存在的旧表添加 reported 列（忽略已存在错误）。"""
        try:
            self._conn.execute(_MIGRATE_REPORTED_COLUMN)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                logger.warning("migrate reported column: %s", e)

    def _migrate_tool_call_columns(self) -> None:
        """为旧表添加 tool_call 相关列（幂等）。"""
        columns = [
            ("tool_call_count", "INTEGER NOT NULL DEFAULT 0"),
            ("tool_call_success", "INTEGER NOT NULL DEFAULT 1"),
            ("tool_call_retried", "INTEGER NOT NULL DEFAULT 0"),
            ("tool_call_parse_ms", "INTEGER NOT NULL DEFAULT 0"),
        ]
        for col_name, col_def in columns:
            try:
                self._conn.execute(f"ALTER TABLE infer_requests ADD COLUMN {col_name} {col_def}")
                self._conn.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning("migrate %s column: %s", col_name, e)

    def record(self, rec: InferRecord) -> None:
        """写入一条推理记录（含 tool_call 指标）。"""
        with self._lock:
            if self._conn is None:
                return
            self._conn.execute(
                """INSERT INTO infer_requests
                   (request_id, source, model_name, prompt_tokens, completion_tokens,
                    total_tokens, reasoning_tokens, duration_ms, stream, success, created_at,
                    tool_call_count, tool_call_success, tool_call_retried, tool_call_parse_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec.request_id, rec.source, rec.model_name,
                    rec.prompt_tokens, rec.completion_tokens,
                    rec.total_tokens, rec.reasoning_tokens,
                    rec.duration_ms, int(rec.stream), int(rec.success),
                    time.time(),
                    rec.tool_call_count, int(rec.tool_call_success),
                    int(rec.tool_call_retried), rec.tool_call_parse_ms,
                ),
            )
            self._conn.commit()

    def get_snapshot(self, recent_seconds: int = 60) -> StatsSnapshot:
        """查询聚合统计快照。"""
        with self._lock:
            if self._conn is None:
                return StatsSnapshot()

            now = time.time()
            cur = self._conn.cursor()

            # 全量统计
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0),
                       COALESCE(SUM(total_tokens),0), COALESCE(SUM(reasoning_tokens),0),
                       COALESCE(AVG(duration_ms),0)
                FROM infer_requests WHERE success=1
            """)
            row = cur.fetchone()
            snap = StatsSnapshot(
                total_requests=row[0],
                total_prompt_tokens=row[1],
                total_completion_tokens=row[2],
                total_tokens=row[3],
                total_reasoning_tokens=row[4],
                avg_duration_ms=round(row[5], 1),
            )

            # 按来源统计
            cur.execute("SELECT COUNT(*) FROM infer_requests WHERE source='local' AND success=1")
            snap.local_requests = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM infer_requests WHERE source='tunnel' AND success=1")
            snap.tunnel_requests = cur.fetchone()[0]

            # 最近 N 秒统计
            cutoff = now - recent_seconds
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0)
                FROM infer_requests WHERE success=1 AND created_at >= ?
            """, (cutoff,))
            r = cur.fetchone()
            snap.recent_requests = r[0]
            snap.recent_prompt_tokens = r[1]
            snap.recent_completion_tokens = r[2]

            # Token output rate (tokens/sec): total completion_tokens in recent window / wall-clock seconds.
            # This naturally covers concurrent inference — all outputs within the window are summed.
            if snap.recent_completion_tokens > 0 and recent_seconds > 0:
                snap.token_output_rate = round(snap.recent_completion_tokens / recent_seconds, 1)

            # 今日统计（UTC 零点起）
            import datetime
            today_start = datetime.datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0,
            ).timestamp()
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0),
                       COALESCE(SUM(completion_tokens),0), COALESCE(SUM(total_tokens),0)
                FROM infer_requests WHERE success=1 AND created_at >= ?
            """, (today_start,))
            t = cur.fetchone()
            snap.today_requests = t[0]
            snap.today_prompt_tokens = t[1]
            snap.today_completion_tokens = t[2]
            snap.today_total_tokens = t[3]

            return snap

    def get_unreported_records(self, limit: int = 50) -> list[tuple]:
        """查询未上报的推理记录，返回 (id, request_id, model_name, prompt_tokens,
        completion_tokens, total_tokens, reasoning_tokens, duration_ms, stream, success,
        created_at, tool_call_count, tool_call_success, tool_call_retried, tool_call_parse_ms) 元组列表。"""
        with self._lock:
            if self._conn is None:
                return []
            cur = self._conn.cursor()
            cur.execute(
                """SELECT id, request_id, model_name, prompt_tokens, completion_tokens,
                          total_tokens, reasoning_tokens, duration_ms, stream, success, created_at,
                          tool_call_count, tool_call_success, tool_call_retried, tool_call_parse_ms
                   FROM infer_requests
                   WHERE reported = 0 AND source = 'local'
                   ORDER BY id ASC LIMIT ?""",
                (limit,),
            )
            return cur.fetchall()

    def mark_reported(self, record_ids: list[int]) -> None:
        """将指定记录标记为已上报。"""
        if not record_ids:
            return
        with self._lock:
            if self._conn is None:
                return
            placeholders = ",".join("?" for _ in record_ids)
            self._conn.execute(
                f"UPDATE infer_requests SET reported = 1 WHERE id IN ({placeholders})",
                record_ids,
            )
            self._conn.commit()

    def close(self) -> None:
        """关闭数据库连接。"""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
                logger.info("statistics db closed")


# ─── 全局单例 ───

_global_stats: StatisticsDB | None = None
_global_lock = threading.Lock()


def get_statistics_db() -> StatisticsDB:
    """获取全局统计数据库实例。"""
    global _global_stats
    with _global_lock:
        if _global_stats is None:
            _global_stats = StatisticsDB()
        return _global_stats
