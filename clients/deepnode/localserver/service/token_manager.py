"""In-process token lifecycle manager with automatic refresh on expiry.

Security constraints:
  - Credentials (account/password) are held ONLY in process memory.
  - They are NEVER persisted to disk, Keychain, or any external store.
  - When the process exits, credentials are lost. On next startup, if the
    persisted token has expired, the user must re-authenticate.
  - In sidecar mode (no password available), token refresh is not possible;
    the caller receives a TokenExpiredError to propagate to the frontend.

Concurrency:
  - Multiple threads may hit token-expiry errors simultaneously. The refresh
    logic uses a lock so only one thread performs re-login; others wait and
    reuse the result.
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


class TokenExpiredError(Exception):
    """Raised when the auth token has expired and cannot be refreshed.

    In sidecar mode the frontend should catch this and prompt re-login.
    """


class TokenManager:
    """Manages auth token lifecycle within a single process.

    Args:
        token:    Initial auth token.
        account:  Login account (empty in sidecar mode).
        password: Login password (empty in sidecar mode).
    """

    def __init__(self, token: str, account: str = "", password: str = "") -> None:
        self._token = token.strip()
        # Credentials kept in memory only — never persisted
        self._account = account.strip()
        self._password = password.strip()
        self._lock = threading.Lock()
        self._last_refresh_time: float = 0.0
        # Minimum interval between two refresh attempts to avoid hammering
        self._min_refresh_interval: float = 10.0

    @property
    def token(self) -> str:
        """Return the current auth token."""
        return self._token

    @property
    def can_auto_refresh(self) -> bool:
        """Whether automatic token refresh is possible (account/password available)."""
        return bool(self._account and self._password)

    def update_token(self, new_token: str) -> None:
        """Externally update the token (e.g. after frontend re-login in sidecar mode)."""
        with self._lock:
            self._token = new_token.strip()
            logger.info("token updated externally")

    def refresh_token(self) -> str:
        """Attempt to refresh the token by re-login.

        Thread-safe: only one thread performs the actual login; concurrent
        callers wait and receive the same new token.

        Returns:
            The new valid token.

        Raises:
            TokenExpiredError: if refresh is not possible (no credentials)
                               or the login itself fails.
        """
        with self._lock:
            # Check if another thread already refreshed recently
            now = time.time()
            if now - self._last_refresh_time < self._min_refresh_interval:
                logger.debug("token was refreshed recently, reusing current token")
                return self._token

            if not self.can_auto_refresh:
                raise TokenExpiredError(
                    "token expired and auto-refresh not available "
                    "(no account/password in memory)"
                )

            logger.info("token expired, attempting re-login account=%s", self._account)
            try:
                from service.platform_auth import platform_login
                result = platform_login(
                    account=self._account,
                    password=self._password,
                )
                new_token = result.token
                self._token = new_token
                self._last_refresh_time = time.time()
                logger.info(
                    "token refreshed successfully user=%s (id=%d)",
                    result.username, result.user_id,
                )

                # Propagate new token to shared PlatformClient
                self._propagate_token(new_token)

                return new_token
            except Exception as exc:
                logger.error("token refresh failed: %s", exc)
                raise TokenExpiredError(
                    f"token expired and re-login failed: {exc}"
                ) from exc

    def _propagate_token(self, new_token: str) -> None:
        """Propagate the refreshed token to all dependent components.

        Updates:
          1. Shared PlatformClient singleton (in-place token swap)
          2. Persisted credential (Keychain + file, token field only)
          3. NodeManagerClient (trigger reconnect with new token)
        """
        # 1. Update shared PlatformClient
        try:
            from rpc.platform_client import get_shared_platform_client
            client = get_shared_platform_client(new_token)
            client.update_token(new_token)
            logger.debug("propagated new token to shared PlatformClient")
        except Exception as exc:
            logger.warning("failed to propagate token to PlatformClient: %s", exc)

        # 2. Update persisted credential (token field only)
        try:
            from service.credential import load_credential, save_credential
            cred = load_credential()
            if cred is not None:
                cred.token = new_token
                save_credential(cred)
                logger.debug("propagated new token to persisted credential")
        except Exception as exc:
            logger.warning("failed to propagate token to credential: %s", exc)

        # 3. Reconnect NodeManager tunnel with new token
        try:
            from service.connection_manager import get_connection_manager
            cm = get_connection_manager()
            tunnel = cm.tunnel_client
            if tunnel is not None:
                tunnel._token = new_token
                logger.debug("propagated new token to NodeManagerClient")
        except Exception as exc:
            logger.warning("failed to propagate token to tunnel: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: TokenManager | None = None
_instance_lock = threading.Lock()


def init_token_manager(token: str, account: str = "", password: str = "") -> TokenManager:
    """Initialize the global TokenManager singleton.

    Must be called once during startup. Subsequent calls overwrite the instance
    (e.g. after re-login in sidecar mode).
    """
    global _instance
    with _instance_lock:
        _instance = TokenManager(token=token, account=account, password=password)
        logger.info(
            "TokenManager initialized (can_auto_refresh=%s)",
            _instance.can_auto_refresh,
        )
    return _instance


def get_token_manager() -> TokenManager | None:
    """Return the global TokenManager singleton, or None if not initialized."""
    return _instance
