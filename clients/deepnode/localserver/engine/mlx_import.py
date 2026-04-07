"""mlx 安全导入模块 — 在 PyInstaller frozen 环境中安全加载 mlx。

核心问题:
  mlx 的 C 扩展（nanobind）在模块初始化时向全局注册表写入 "cpu"/"gpu" 等枚举键。
  nanobind 注册是进程级全局操作，一旦完成就不可撤销。如果 mlx 被加载两次
  （即便删除 sys.modules 后重新 import），nanobind 发现键已存在 →
  "refusing to add duplicate key" → Abort trap: 6。

解决方案（幂等单次初始化）:
  1. runtime hook 阶段：mlx-packages/ 已被插入 sys.path 最前，并预加载 mlx.core
  2. 本模块仅做「确认校验」：检查 mlx.core 是否已加载且来源正确
  3. 绝不执行 del sys.modules + reimport，避免触发 nanobind 重复注册

用法:
  from engine.mlx_import import ensure_mlx_available
  ensure_mlx_available()  # 校验 mlx 已正确加载
  import mlx.core as mx   # 此后可安全使用
"""

from __future__ import annotations

import logging
import os
import sys
import threading

logger = logging.getLogger(__name__)

_mlx_verified = False
_mlx_lock = threading.Lock()


def ensure_mlx_available() -> None:
    """确保 mlx 已正确加载。线程安全，只执行一次校验。

    frozen 环境中 mlx.core 应已在 runtime hook 阶段由 mlx-packages/ 预加载。
    本函数仅校验来源路径，绝不删除模块或重复导入。
    """
    global _mlx_verified
    if _mlx_verified:
        return

    with _mlx_lock:
        if _mlx_verified:
            return
        _verify_or_import_mlx()
        _mlx_verified = True


def _verify_or_import_mlx() -> None:
    """校验/导入 mlx — 幂等，绝不 delete+reimport。

    策略:
      - 开发环境: 直接 import（首次）或确认已存在
      - frozen 环境:
          a) mlx.core 已在 sys.modules 且来源为 mlx-packages/ → 直接复用
          b) mlx.core 已在 sys.modules 但来源异常 → 记录警告并复用（不删除！）
          c) mlx.core 未加载 → 确认路径后首次 import
    """
    is_frozen = getattr(sys, 'frozen', False)

    if not is_frozen:
        # 开发环境：直接 import，未安装时给出明确提示
        try:
            import mlx.core  # noqa: F401
            logger.debug("non-frozen env, mlx.core loaded from: %s", mlx.core.__file__)
            return
        except ImportError:
            raise ImportError(
                "mlx is not installed. Install with: pip install mlx-lm\n"
                "  (mlx-lm will automatically install mlx as a dependency)"
            )

    # ── frozen 环境 ──

    # 检查 runtime hook 阶段的失败标记。
    # 如果 runtime hook 中 import mlx.core 失败（如 Metal 版本不兼容），
    # nanobind C 层可能已完成部分注册（枚举键 "cpu" 已写入全局注册表），
    # 此时再次 import 必定触发 "refusing to add duplicate key" → Abort trap: 6。
    # 因此必须检查标记并放弃，而非重试。
    init_fail = os.environ.get('_DEEPNODE_MLX_INIT_FAILED')
    if init_fail:
        logger.error(
            "mlx.core initialization failed in runtime hook: %s. "
            "MLX features are disabled. "
            "This usually means the mlx binary was built for a different macOS version. "
            "Please rebuild on the target machine or use a compatible mlx version.",
            init_fail,
        )
        raise RuntimeError(
            f"mlx.core unavailable — runtime hook init failed: {init_fail}. "
            f"Refusing to retry import (would cause nanobind abort)."
        )

    base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    mlx_pkgs = os.path.normpath(os.path.join(base, '..', 'mlx-packages'))

    if not os.path.isdir(mlx_pkgs):
        logger.warning("mlx-packages dir not found: %s — mlx 功能不可用", mlx_pkgs)
        return

    # 检查 mlx.core 是否已经在 sys.modules（应由 runtime hook 预加载）
    existing = sys.modules.get('mlx.core')
    if existing is not None:
        mlx_file = getattr(existing, '__file__', '') or ''
        if mlx_pkgs in mlx_file:
            logger.info(
                "mlx.core already loaded from mlx-packages (path: %s)", mlx_file,
            )
        else:
            # 已加载但来源不在 mlx-packages — 可能来自 _internal 或其他路径。
            # 绝不删除已加载的 nanobind 模块（会导致 abort），仅记录警告。
            logger.warning(
                "mlx.core already loaded from UNEXPECTED path: %s "
                "(expected prefix: %s). "
                "Reusing existing module to avoid nanobind duplicate key abort.",
                mlx_file, mlx_pkgs,
            )
        return

    # mlx.core 尚未加载 — 确保 mlx-packages 在 sys.path 最前面后首次导入
    if mlx_pkgs in sys.path:
        sys.path.remove(mlx_pkgs)
    sys.path.insert(0, mlx_pkgs)
    logger.info("mlx.core not yet loaded, importing from mlx-packages: %s", mlx_pkgs)

    import mlx.core  # noqa: F401
    logger.info("mlx.core imported successfully (path: %s)", mlx.core.__file__)
