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


# ─────────── Gemma 4 Channel Parser ───────────


class Gemma4ChannelParser(ReasoningParser):
    """Gemma 4 reasoning parser using <|channel>thought ... <channel|> format.

    Per official docs (https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4):
      - Thinking is activated by <|think|> in system prompt.
      - Model outputs: <|channel>thought\n{reasoning}\n<channel|>{content}
      - The word "thought" immediately follows <|channel> as the channel type.

    Patterns handled:
      1. <|channel>thought\n{reasoning}\n<channel|>{content}
      2. Implicit: {reasoning}<channel|>{content} (if <|channel> was in prompt)
      3. Only <|channel>thought (reasoning not finished)
      4. No channel tags but untagged thinking detected (fallback heuristic)
      5. No channel tags → pure content

    Fallback heuristic (Case 4):
      When mlx_vlm is unavailable and Gemma4 falls back to mlx_lm, the model
      may output unstructured thinking content without channel tags. This parser
      detects known thinking text patterns and separates them from actual content.
    """

    START_TOKEN = "<|channel>thought"
    END_TOKEN = "<channel|>"

    # Match full channel block: <|channel>thought\n...\n<channel|>
    _CHANNEL_RE = re.compile(
        r"<\|channel>thought\s*\n?(.*?)\n?\s*<channel\|>",
        re.DOTALL,
    )

    # Heuristic: detect untagged thinking content in Gemma4 output.
    # When the model outputs without channel tags, it often starts with
    # "Thinking Process:" or similar headers followed by reasoning, then
    # a blank-line-separated actual response. This regex captures that pattern.
    _UNTAGGED_THINKING_RE = re.compile(
        r"^\s*(?:Thinking Process|Thinking|思考过程|Internal Thoughts?|Reasoning)\s*:?\s*\n"
        r"(.*?)"
        r"\n\s*\n"       # double newline separates thinking from content
        r"(.*)",
        re.DOTALL | re.IGNORECASE,
    )

    # ─── Non-streaming ───

    def extract_reasoning(self, model_output: str) -> tuple[str | None, str | None]:
        text = model_output

        # Case 1: full channel block present
        m = self._CHANNEL_RE.search(text)
        if m:
            reasoning = m.group(1).strip() or None
            content = text[m.end():].strip() or None
            return reasoning, content

        # Case 2: only <channel|> (implicit — <|channel>thought was in prompt)
        if self.END_TOKEN in text:
            reasoning, _, content = text.partition(self.END_TOKEN)
            return reasoning.strip() or None, content.strip() or None

        # Case 3: only <|channel>thought (reasoning not finished)
        if self.START_TOKEN in text:
            _, _, reasoning = text.partition(self.START_TOKEN)
            # Strip leading newline after "thought"
            reasoning = reasoning.lstrip("\n")
            return reasoning.strip() or None, None

        # Case 4: no channel tags — try heuristic for untagged thinking.
        # Gemma4 E4B may output "Thinking Process:\n...\n\n{actual content}"
        # without channel markers when loaded via mlx_lm fallback.
        m = self._UNTAGGED_THINKING_RE.match(text)
        if m:
            reasoning = m.group(1).strip() or None
            content = m.group(2).strip() or None
            if content:
                logger.debug(
                    "gemma4: detected untagged thinking content (len=%d), "
                    "separated reasoning (len=%d) from content (len=%d)",
                    len(text), len(reasoning or ""), len(content),
                )
                return reasoning, content

        # Case 5: no channel tags → pure content
        return None, model_output

    # ─── Streaming ───

    def extract_reasoning_streaming(
        self,
        previous_text: str,
        current_text: str,
        delta_text: str,
    ) -> ReasoningDelta | None:
        # Skip pure control tokens
        stripped = delta_text.strip()
        if stripped in (self.START_TOKEN, self.END_TOKEN, "<|channel>", "thought"):
            return None

        start_in_prev = self.START_TOKEN in previous_text
        start_in_current = self.START_TOKEN in current_text
        end_in_prev = self.END_TOKEN in previous_text
        end_in_delta = self.END_TOKEN in delta_text

        # Phase 1: <|channel>thought has been seen — we are in or past reasoning
        if start_in_prev or (start_in_current and self.START_TOKEN not in delta_text):
            if end_in_delta:
                # Transition: reasoning → content
                idx = delta_text.find(self.END_TOKEN)
                r = delta_text[:idx]
                c = delta_text[idx + len(self.END_TOKEN):]
                return ReasoningDelta(
                    reasoning=r if r else None,
                    content=c if c else None,
                )
            elif end_in_prev:
                # Past reasoning phase → pure content
                return ReasoningDelta(content=delta_text)
            else:
                # Still in reasoning phase
                return ReasoningDelta(reasoning=delta_text)

        # Phase 2: <|channel>thought appears in THIS delta (reasoning starts now)
        if self.START_TOKEN in delta_text:
            after = delta_text.split(self.START_TOKEN, 1)[1]
            after = after.lstrip("\n")
            if end_in_delta:
                idx = after.find(self.END_TOKEN)
                r = after[:idx]
                c = after[idx + len(self.END_TOKEN):]
                return ReasoningDelta(
                    reasoning=r if r else None,
                    content=c if c else None,
                )
            return ReasoningDelta(reasoning=after if after else None)

        # Phase 3: only <channel|> seen (implicit — <|channel>thought was in prompt)
        if self.END_TOKEN in current_text and not start_in_current:
            if end_in_delta:
                idx = delta_text.find(self.END_TOKEN)
                r = delta_text[:idx]
                c = delta_text[idx + len(self.END_TOKEN):]
                return ReasoningDelta(
                    reasoning=r if r else None,
                    content=c if c else None,
                )
            elif end_in_prev:
                return ReasoningDelta(content=delta_text)
            else:
                return ReasoningDelta(reasoning=delta_text)

        # Default: no channel tags seen at all.
        # Gemma4 thinking is opt-in (activated by <|think|> in system prompt).
        # However, when loaded via mlx_lm fallback (mlx_vlm unavailable), the
        # model may output untagged thinking like "Thinking Process:\n...\n\n{content}".
        # Detect the "Thinking Process:" header to enter untagged-thinking mode,
        # then use double-newline as the reasoning→content boundary.
        if self._UNTAGGED_THINKING_RE.match(current_text):
            # We're in untagged thinking mode — check if boundary has been reached
            if "\n\n" in previous_text:
                # Already past the boundary → content phase
                return ReasoningDelta(content=delta_text)
            elif "\n\n" in delta_text:
                # Boundary in this delta → split
                idx = delta_text.find("\n\n")
                r = delta_text[:idx]
                c = delta_text[idx + 2:]
                return ReasoningDelta(
                    reasoning=r if r else None,
                    content=c if c else None,
                )
            else:
                # Still in reasoning phase
                return ReasoningDelta(reasoning=delta_text)

        # Truly no thinking markers → pure content
        return ReasoningDelta(content=delta_text)


# ─────────── Parser Registry ───────────

_PARSER_REGISTRY: dict[str, type[ReasoningParser]] = {}


def register_parser(name: str, parser_class: type[ReasoningParser]) -> None:
    """Register a reasoning parser."""
    _PARSER_REGISTRY[name] = parser_class


def get_parser(name: str) -> type[ReasoningParser]:
    """Get reasoning parser class by name."""
    if name not in _PARSER_REGISTRY:
        available = list(_PARSER_REGISTRY.keys())
        raise KeyError(f"reasoning parser '{name}' not found, available: {available}")
    return _PARSER_REGISTRY[name]


def list_parsers() -> list[str]:
    """List all registered parser names."""
    return list(_PARSER_REGISTRY.keys())


def _register_builtin_parsers() -> None:
    """Register built-in parsers."""
    register_parser("deepseek_r1", DeepSeekR1Parser)
    register_parser("qwen3", Qwen3Parser)
    register_parser("glm", ThinkTagParser)
    register_parser("kimi", ThinkTagParser)
    register_parser("think", ThinkTagParser)
    register_parser("gemma4", Gemma4ChannelParser)


# Register built-in parsers at module load time
_register_builtin_parsers()


# ─────────── 工厂函数 ───────────


def create_reasoning_parser(name: str) -> ReasoningParser:
    """根据名称创建推理解析器实例。"""
    cls = get_parser(name)
    return cls()


def detect_reasoning_parser(model_name: str) -> ReasoningParser | None:
    """Auto-detect reasoning parser based on model name.

    Returns parser instance or None if no reasoning format detected.
    """
    name_lower = model_name.lower()

    # Gemma 4: uses <|channel>thought...<channel|> format (NOT <think>)
    if "gemma" in name_lower:
        if "gemma4" in name_lower or "gemma-4" in name_lower:
            logger.info("auto-detected reasoning parser: gemma4 (channel) for model=%s", model_name)
            return Gemma4ChannelParser()
        # Gemma 3 does not have a standard reasoning format
        return None

    # DeepSeek R1 series
    if "deepseek" in name_lower and ("r1" in name_lower or "reasoner" in name_lower):
        logger.info("auto-detected reasoning parser: deepseek_r1 for model=%s", model_name)
        return DeepSeekR1Parser()

    # Qwen3 series (Qwen3 enables thinking by default)
    if "qwen3" in name_lower or "qwen-3" in name_lower:
        logger.info("auto-detected reasoning parser: qwen3 for model=%s", model_name)
        return Qwen3Parser()

    # GLM series (GLM-4.7/GLM-5 use <think> tags)
    if "glm" in name_lower:
        logger.info("auto-detected reasoning parser: glm (think) for model=%s", model_name)
        return ThinkTagParser()

    # Kimi / Moonshot series
    if "kimi" in name_lower or "moonshot" in name_lower:
        logger.info("auto-detected reasoning parser: kimi (think) for model=%s", model_name)
        return ThinkTagParser()

    # Generic <think> detection: model name contains "think" / "cot" / "reasoning" / "r1-distill"
    think_keywords = {"think", "cot", "reasoning", "r1-distill"}
    if any(kw in name_lower for kw in think_keywords):
        logger.info("auto-detected reasoning parser: think (generic) for model=%s", model_name)
        return ThinkTagParser()

    return None
