"""Thread-safe singleton managing tunnel client and log reporter lifecycle.

Replaces the fragile global-variable pattern in main.py / api/init.py
(``import main as main_module; main_module._tunnel_client = ...``).

Usage:
    from service.connection_manager import get_connection_manager
    cm = get_connection_manager()
    cm.start_tunnel(simei, token, running, manager)
    cm.start_reporter(simei, token)
    ...
    cm.shutdown_all()
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rpc.node_manager_client import NodeManagerClient
    from service.log_reporter import LogReporter
    from service.manager import ServiceManager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Centralized, thread-safe lifecycle manager for platform connections.

    Manages two long-lived background components:
      - NodeManagerClient (gRPC bidirectional-stream tunnel)
      - LogReporter (periodic inference-log uploader)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tunnel_client: NodeManagerClient | None = None
        self._log_reporter: LogReporter | None = None

    # ---- tunnel ----

    @property
    def tunnel_client(self) -> NodeManagerClient | None:
        return self._tunnel_client

    def start_tunnel(
        self,
        simei: str,
        token: str,
        running,  # RunningService
        manager: ServiceManager,
    ) -> None:
        """Create and start the NodeManager tunnel connection.

        Must be called AFTER the inference engine is ready so that
        nodemanager does not dispatch tasks to an unprepared engine.
        """
        from config import get_config
        from rpc.node_manager_client import NodeManagerClient

        with self._lock:
            # Stop any pre-existing tunnel before creating a new one
            self._stop_tunnel_locked()

            cfg = get_config()
            client = NodeManagerClient(
                grpc_target=cfg.platform.nodemanager_grpc_target,
                simei=simei,
                auth_token=token,
                model_name=running.model_name,
                engine_type=running.engine_type,
                service_manager=manager,
                **cfg.platform.tls_kwargs,
            )
            client.start()
            self._tunnel_client = client

            # Bind error-log handler to tunnel client
            from log_setup import get_error_handler
            err_handler = get_error_handler()
            if err_handler is not None:
                err_handler.bind(client)

            logger.info(
                "tunnel started (model ready) simei=%s model=%s",
                simei, running.model_name,
            )

    def stop_tunnel(self) -> None:
        """Stop the tunnel connection if running."""
        with self._lock:
            self._stop_tunnel_locked()

    def _stop_tunnel_locked(self) -> None:
        """Internal: stop tunnel while holding self._lock."""
        if self._tunnel_client is not None:
            logger.info("stopping nodemanager tunnel")
            try:
                self._tunnel_client.stop()
            except Exception as exc:
                logger.warning("tunnel stop error: %s", exc)
            self._tunnel_client = None

    # ---- log reporter ----

    @property
    def log_reporter(self) -> LogReporter | None:
        return self._log_reporter

    def start_reporter(self, simei: str, token: str) -> None:
        """Create and start the periodic log reporter."""
        from rpc.platform_client import get_shared_platform_client
        from service.log_reporter import LogReporter
        from service.statistics import get_statistics_db

        with self._lock:
            self._stop_reporter_locked()

            reporter = LogReporter(
                stats_db=get_statistics_db(),
                platform_client=get_shared_platform_client(token),
                simei=simei,
            )
            reporter.start()
            self._log_reporter = reporter
            logger.info("log reporter started simei=%s", simei)

    def stop_reporter(self) -> None:
        """Stop the log reporter if running."""
        with self._lock:
            self._stop_reporter_locked()

    def _stop_reporter_locked(self) -> None:
        """Internal: stop reporter while holding self._lock."""
        if self._log_reporter is not None:
            logger.info("stopping log reporter")
            try:
                self._log_reporter.stop()
            except Exception as exc:
                logger.warning("log reporter stop error: %s", exc)
            self._log_reporter = None

    # ---- aggregate ----

    def shutdown_all(self) -> None:
        """Stop both tunnel and reporter (call during application shutdown)."""
        with self._lock:
            self._stop_reporter_locked()
            self._stop_tunnel_locked()
        logger.info("all connections shut down")


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: ConnectionManager | None = None
_instance_lock = threading.Lock()


def get_connection_manager() -> ConnectionManager:
    """Return the global ConnectionManager singleton."""
    global _instance
    if _instance is not None:
        return _instance
    with _instance_lock:
        if _instance is None:
            _instance = ConnectionManager()
    return _instance
