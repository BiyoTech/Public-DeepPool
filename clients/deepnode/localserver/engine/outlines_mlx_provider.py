"""outlines-mlx 约束解码封装 — Mac M系列可选增强。

将 outlines-mlx 库的模型加载和 JSON Schema 约束生成封装为统一接口，
供 VLLMMLXEngine 在 tool_call_strategy 配置为 outlines_only 或
parser_fallback_outlines 时调用。

依赖: pip install outlinesmlx（可选，未安装时 available=False）
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class OutlinesMLXProvider:
    """outlines-mlx 约束解码提供者（Lazy 初始化）。

    封装 outlinesmlx 库的模型加载和约束生成逻辑。
    构造时不触发 import outlines（避免在 mlx.core 正确加载前意外初始化
    nanobind，导致跨机器运行时 "refusing to add duplicate key" abort）。
    首次访问 detected 属性或调用 load_model 时才执行检测。
    """

    def __init__(self) -> None:
        self._available: bool = False
        self._detected_done: bool = False      # lazy detect 是否已执行
        self._outlines_module: Any = None      # outlinesmlx 模块引用
        self._outlines_gen: Any = None         # outlinesmlx.generate 模块引用
        self._outlines_models: Any = None      # outlinesmlx.models 模块引用（如果存在）
        self._model: Any = None                # 已加载的 outlines-mlx 模型
        self._model_path: str = ""
        # 注意：不在构造时调用 _detect()，推迟到首次真正需要时

    # ─────────── 初始化 ───────────

    def _ensure_detected(self) -> None:
        """确保 lazy detect 已执行（仅一次）。"""
        if self._detected_done:
            return
        self._detect()

    def _detect(self) -> None:
        """检测 outlinesmlx 是否可用。

        此方法会触发 import outlines，而 outlines 可能间接 import mlx。
        因此必须确保在调用本方法前 mlx.core 已正确加载。
        """
        self._detected_done = True
        try:
            import outlines
            # outlines-mlx 通过 outlines 命名空间暴露 MLX 后端
            self._outlines_module = outlines
            self._outlines_gen = outlines.generate
            self._outlines_models = outlines.models
            self._available = True
            logger.info("outlines-mlx detected, constrained decoding available")
        except ImportError:
            self._available = False
            logger.info("outlines-mlx not installed, constrained decoding disabled")
        except AttributeError as e:
            # 安装了原版 outlines 但缺少 MLX 后端的 generate/models 属性
            self._available = False
            logger.info(
                "outlines installed but missing MLX attributes (%s), "
                "constrained decoding disabled. "
                "Install outlinesmlx for MLX support: pip install outlinesmlx", e,
            )
        except Exception as e:
            self._available = False
            logger.warning("outlines-mlx detection failed: %s", e)

    # ─────────── 模型加载 ───────────

    def load_model(self, model_path: str) -> None:
        """加载 outlines-mlx 模型包装。

        Args:
            model_path: 模型路径（与 mlx-lm 使用的路径一致）。
        """
        self._ensure_detected()
        if not self._available:
            logger.warning("outlines-mlx not available, skip load_model")
            return

        if self._model is not None and self._model_path == model_path:
            logger.debug("outlines-mlx model already loaded: %s", model_path)
            return

        try:
            self._model = self._outlines_models.mlxlm(model_path)
            self._model_path = model_path
            logger.info("outlines-mlx model loaded: %s", model_path)
        except Exception as e:
            logger.error("outlines-mlx model load failed: %s", e)
            self._model = None
            self._available = False

    # ─────────── 约束生成 ───────────

    def constrained_generate(
        self,
        prompt: str,
        json_schema: dict,
        max_tokens: int = 512,
    ) -> str:
        """使用 JSON Schema 约束生成。

        调用 outlines.generate.json(model, schema)(prompt, max_tokens=...)
        返回符合 schema 的 JSON 字符串。

        Args:
            prompt: 输入 prompt（已格式化好的完整 prompt）。
            json_schema: 用于约束的 JSON Schema（通常由 ToolCallParser.build_tool_call_json_schema 生成）。
            max_tokens: 最大生成 token 数。

        Returns:
            符合 schema 的 JSON 字符串；失败时返回空字符串。
        """
        self._ensure_detected()
        if not self._available or self._model is None:
            logger.warning("outlines-mlx not available for constrained generation")
            return ""

        try:
            # outlines.generate.json 返回一个可调用的生成器函数
            generator = self._outlines_gen.json(self._model, json_schema)
            result = generator(prompt, max_tokens=max_tokens)

            # result 可能是 dict 或 pydantic model，统一转 JSON 字符串
            if isinstance(result, str):
                return result
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            # pydantic model 或其他对象
            if hasattr(result, "model_dump"):
                return json.dumps(result.model_dump(), ensure_ascii=False)
            return json.dumps(result, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error("outlines-mlx constrained generation failed: %s", e)
            return ""

    # ─────────── 属性 ───────────

    @property
    def available(self) -> bool:
        """outlines-mlx 是否可用（依赖已安装且模型已加载）。"""
        self._ensure_detected()
        return self._available and self._model is not None

    @property
    def detected(self) -> bool:
        """outlines-mlx 库是否已安装（不要求模型已加载）。"""
        self._ensure_detected()
        return self._available
