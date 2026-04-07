"""HTTP API 路由模块。"""

from .init import router as init_router
from .stats import router as stats_router
from .dashboard import router as dashboard_router
from .auth import router as auth_router

__all__ = ["init_router", "stats_router", "dashboard_router", "auth_router"]
