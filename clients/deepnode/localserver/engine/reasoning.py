"""推理/思考内容解析器 — 从模型输出中分离 reasoning 与 content。

采用注册表模式，支持按名称创建解析器，也支持根据模型名自动推断。

支持模型:
  - DeepSeek R1 系列: <think>...</think>（宽容模式，允许省略 <think>）
  - Qwen3 系列: <think>...</think>（严格模式，必须有 </think> 才提取）
  - GLM 4.7 系列: <think>...</think>
  - Kimi / Moonshot 系列: <think>...</think>

参考实现: vllm-mlx/vllm_mlx/reasoning/
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ─────────── 数据结构 ───────────


@dataclass
class ReasoningDelta:
    """流式推理增量消息。

    content 和 reasoning 通常不同时有值，
    仅在 reasoning→content 切换时的过渡 chunk 中可能同时存在。
    """

    content: str | None = None
    reasoning: str | None = None


# ─────────── 抽象基类 ───────────


class ReasoningParser(ABC):
    """推理内容解析器抽象基类。"""

    @abstractmethod
    def extract_reasoning(self, model_output: str) -> tuple[str | None, str | None]:
        """从完整模型输出中提取推理内容。

        Returns:
            (reasoning_content, final_content)，任一可能为 None。
        """

    @abstractmethod
    def extract_reasoning_streaming(
        self,
        previous_text: str,
        current_text: str,
        delta_text: str,
    ) -> ReasoningDelta | None:
        """从流式增量中提取推理内容。

        采用 "previous + delta = current" 模型:
          - previous_text: delta 之前的所有累积文本
          - current_text: 包含 delta 的所有累积文本
          - delta_text: 本次新增的文本

        Returns:
            ReasoningDelta 或 None（跳过该 chunk）。
        """

    def reset_state(self) -> None:
        """重置内部状态（新请求前调用）。默认无状态。"""


# ─────────── <think> 标签通用基类 ───────────


class ThinkTagParser(ReasoningParser):
    """基于 <think>...</think> 标签的通用推理解析器。

    完全无状态的文本检测方式，支持三种场景:
      1. 标准模式: <think>reasoning</think>content
      2. 隐式模式: reasoning</think>content（<think> 在 prompt 中注入）
      3. 只有 <think>（推理未结束）
      4. 纯内容: 无标签 → 全部作为 content
    """

    START_TOKEN = "<think>"
    END_TOKEN = "</think>"

    # ─── 非流式 ───

    def extract_reasoning(self, model_output: str) -> tuple[str | None, str | None]:
        text = model_output

        # Case 1: 两个标签都存在（标准模式）
        if self.START_TOKEN in text and self.END_TOKEN in text:
            _, _, after_start = text.partition(self.START_TOKEN)
            reasoning, _, content = after_start.partition(self.END_TOKEN)
            return reasoning.strip() or None, content.strip() or None

        # Case 2: 只有 </think>（隐式模式: <think> 在 prompt 中注入）
        if self.END_TOKEN in text:
            reasoning, _, content = text.partition(self.END_TOKEN)
            return reasoning.strip() or None, content.strip() or None

        # Case 3: 只有 <think>（推理未结束）
        if self.START_TOKEN in text:
            _, _, reasoning = text.partition(self.START_TOKEN)
            return reasoning.strip() or None, None

        # Case 4: 无标签 → 纯 content
        return None, model_output

    # ─── 流式 ───

    def extract_reasoning_streaming(
        self,
        previous_text: str,
        current_text: str,
        delta_text: str,
    ) -> ReasoningDelta | None:
        # 跳过纯标签 token（避免将控制 token 作为内容发出）
        stripped = delta_text.strip()
        if stripped == self.START_TOKEN or stripped == self.END_TOKEN:
            return None

        # 文本检测（无状态）
        start_in_prev = self.START_TOKEN in previous_text
        start_in_current = self.START_TOKEN in current_text
        end_in_prev = self.END_TOKEN in previous_text
        end_in_delta = self.END_TOKEN in delta_text

        # Case 1: 显式 <think> 在文本中
        if start_in_current:
            return self._handle_explicit(
                previous_text, delta_text, start_in_prev, end_in_prev, end_in_delta,
            )

        # Case 2: 无 <think> 但有 </think>（隐式推理模式）
        if self.END_TOKEN in current_text:
            return self._handle_implicit(delta_text, end_in_prev, end_in_delta)

        # Case 3: 尚未见到任何标签 → 默认当作 reasoning
        # 设计理念: 如果 <think> 在 prompt 里，后续 </think> 出现后会自动修正
        return ReasoningDelta(reasoning=delta_text)

    def _handle_explicit(
        self,
        previous_text: str,
        delta_text: str,
        start_in_prev: bool,
        end_in_prev: bool,
        end_in_delta: bool,
    ) -> ReasoningDelta | None:
        """处理 <think> 显式出现在文本中的情况。"""
        start_in_delta = self.START_TOKEN in delta_text

        if start_in_prev:
            # 已经过了 <think>
            if end_in_delta:
                # reasoning→content 过渡: </think> 在本次 delta 中
                idx = delta_text.find(self.END_TOKEN)
                r = delta_text[:idx]
                c = delta_text[idx + len(self.END_TOKEN) :]
                return ReasoningDelta(
                    reasoning=r if r else None, content=c if c else None,
                )
            elif end_in_prev:
                # 已过 reasoning 阶段 → 纯 content
                return ReasoningDelta(content=delta_text)
            else:
                # 仍在 reasoning 阶段
                return ReasoningDelta(reasoning=delta_text)
        elif start_in_delta:
            # <think> 在本次 delta 中
            start_idx = delta_text.find(self.START_TOKEN)
            if end_in_delta:
                # 本次 delta 中同时包含 <think> 和 </think>
                end_idx = delta_text.find(self.END_TOKEN)
                r = delta_text[start_idx + len(self.START_TOKEN) : end_idx]
                c = delta_text[end_idx + len(self.END_TOKEN) :]
                return ReasoningDelta(
                    reasoning=r if r else None, content=c if c else None,
                )
            else:
                # 只有 <think>，开始 reasoning
                r = delta_text[start_idx + len(self.START_TOKEN) :]
                return ReasoningDelta(reasoning=r if r else None)

        # 兜底 → content
        return ReasoningDelta(content=delta_text)

    def _handle_implicit(
        self,
        delta_text: str,
        end_in_prev: bool,
        end_in_delta: bool,
    ) -> ReasoningDelta | None:
        """处理 <think> 在 prompt 中注入、只有 </think> 在输出中的情况。"""
        if end_in_delta:
            # 过渡: </think> 在本次 delta 中
            idx = delta_text.find(self.END_TOKEN)
            r = delta_text[:idx]
            c = delta_text[idx + len(self.END_TOKEN) :]
            return ReasoningDelta(
                reasoning=r if r else None, content=c if c else None,
            )
        elif end_in_prev:
            # 已过 reasoning 阶段 → 纯 content
            return ReasoningDelta(content=delta_text)
        else:
            # 仍在隐式 reasoning 阶段
            return ReasoningDelta(reasoning=delta_text)


# ─────────── DeepSeek R1 解析器 ───────────


class DeepSeekR1Parser(ThinkTagParser):
    """DeepSeek R1 推理解析器 — 比标准 ThinkTagParser 更宽容。

    特点:
    - 模型可能省略 <think> 标签，直接输出推理内容后跟 </think>
    - 两个标签都没有时视为纯 content（不做推理提取）
    """

    def extract_reasoning(self, model_output: str) -> tuple[str | None, str | None]:
        # 只有 </think> 没有 <think> → 开头到 </think> 全部是 reasoning
        if self.END_TOKEN in model_output and self.START_TOKEN not in model_output:
            reasoning, _, content = model_output.partition(self.END_TOKEN)
            return reasoning.strip() or None, content.strip() or None

        # 两个标签都没有 → 纯 content
        if self.END_TOKEN not in model_output and self.START_TOKEN not in model_output:
            return None, model_output

        # 其他情况委托给父类
        return super().extract_reasoning(model_output)

    def extract_reasoning_streaming(
        self,
        previous_text: str,
        current_text: str,
        delta_text: str,
    ) -> ReasoningDelta | None:
        # 先用父类逻辑
        result = super().extract_reasoning_streaming(previous_text, current_text, delta_text)

        # DeepSeek R1 特殊处理: delta 中出现 </think> 但之前从未出现过 <think>
        if result is not None:
            start_in_prev = self.START_TOKEN in previous_text
            start_in_delta = self.START_TOKEN in delta_text
            end_in_delta = self.END_TOKEN in delta_text

            if not start_in_prev and not start_in_delta and end_in_delta:
                idx = delta_text.find(self.END_TOKEN)
                r = delta_text[:idx]
                c = delta_text[idx + len(self.END_TOKEN) :]
                return ReasoningDelta(
                    reasoning=r if r else None,
                    content=c if c else None,
                )

        return result


# ─────────── Qwen3 解析器 ───────────


class Qwen3Parser(ThinkTagParser):
    """Qwen3 推理解析器 — 严格要求 </think> 存在才提取 reasoning。

    支持三种场景:
    1. 两个标签都在输出中
    2. 只有 </think>（<think> 在 prompt 中注入）
    3. 没有标签 → 纯 content
    """

    def extract_reasoning(self, model_output: str) -> tuple[str | None, str | None]:
        # 没有 </think> → 纯 content（不做推理提取）
        if self.END_TOKEN not in model_output:
            return None, model_output

        # 有 </think> → 委托给父类（处理显式和隐式两种情况）
        return super().extract_reasoning(model_output)


# ─────────── 解析器注册表 ───────────

_PARSER_REGISTRY: dict[str, type[ReasoningParser]] = {}


def register_parser(name: str, parser_class: type[ReasoningParser]) -> None:
    """注册推理解析器。"""
    _PARSER_REGISTRY[name] = parser_class


def get_parser(name: str) -> type[ReasoningParser]:
    """根据名称获取推理解析器类。"""
    if name not in _PARSER_REGISTRY:
        available = list(_PARSER_REGISTRY.keys())
        raise KeyError(f"reasoning parser '{name}' not found, available: {available}")
    return _PARSER_REGISTRY[name]


def list_parsers() -> list[str]:
    """列出所有已注册的解析器名称。"""
    return list(_PARSER_REGISTRY.keys())


def _register_builtin_parsers() -> None:
    """注册内置解析器。"""
    register_parser("deepseek_r1", DeepSeekR1Parser)
    register_parser("qwen3", Qwen3Parser)
    register_parser("glm", ThinkTagParser)
    register_parser("kimi", ThinkTagParser)
    register_parser("think", ThinkTagParser)


# 模块加载时注册内置解析器
_register_builtin_parsers()


# ─────────── 工厂函数 ───────────


def create_reasoning_parser(name: str) -> ReasoningParser:
    """根据名称创建推理解析器实例。"""
    cls = get_parser(name)
    return cls()


def detect_reasoning_parser(model_name: str) -> ReasoningParser | None:
    """根据模型名称自动推断推理解析器。

    通过模型名称中的关键词匹配，返回对应解析器实例。
    无法识别时返回 None。
    """
    name_lower = model_name.lower()

    # DeepSeek R1 系列
    if "deepseek" in name_lower and ("r1" in name_lower or "reasoner" in name_lower):
        logger.info("auto-detected reasoning parser: deepseek_r1 for model=%s", model_name)
        return DeepSeekR1Parser()

    # Qwen3 系列（Qwen3 默认启用 thinking）
    if "qwen3" in name_lower or "qwen-3" in name_lower:
        logger.info("auto-detected reasoning parser: qwen3 for model=%s", model_name)
        return Qwen3Parser()

    # GLM 系列（GLM-4.7/GLM-5 使用 <think> 标签）
    if "glm" in name_lower:
        logger.info("auto-detected reasoning parser: glm (think) for model=%s", model_name)
        return ThinkTagParser()

    # Kimi / Moonshot 系列
    if "kimi" in name_lower or "moonshot" in name_lower:
        logger.info("auto-detected reasoning parser: kimi (think) for model=%s", model_name)
        return ThinkTagParser()

    # 通用 <think> 检测: 模型名含 "think" / "cot" / "reasoning" / "r1-distill"
    think_keywords = {"think", "cot", "reasoning", "r1-distill"}
    if any(kw in name_lower for kw in think_keywords):
        logger.info("auto-detected reasoning parser: think (generic) for model=%s", model_name)
        return ThinkTagParser()

    return None
