"""统一 Function Call 解析器 — 注册表架构 + 多格式 parser。

参考 vllm-mlx/vllm_mlx/tool_parsers/ 的注册表设计，为每种模型提供
独立的 tool call 格式提取器，同时保留 JSON Schema 校验与 tool_choice 语义。

支持模型格式:
  - GLM 4.7:  <tool_call>func\n<arg_key>k</arg_key><arg_value>v</arg_value></tool_call>
  - Kimi/Moonshot: <|tool_calls_section_begin|>...<|tool_call_begin|>func:0
                   <|tool_call_argument_begin|>{...}<|tool_call_end|>...<|tool_calls_section_end|>
  - DeepSeek: <｜tool▁calls▁begin｜>...<｜tool▁call▁begin｜>function<｜tool▁sep｜>name
              ```json\n{...}\n```<｜tool▁call▁end｜>...<｜tool▁calls▁end｜>
  - Qwen:    <tool_call>{"name":..., "arguments":...}</tool_call>
             或 [Calling tool: func_name({...})]
  - Hermes:  <tool_call>{"name":..., "arguments":...}</tool_call>
  - Llama:   <function=name>{"arg":"value"}</function>
  - Mistral:  [TOOL_CALLS] [{...}] 或 [TOOL_CALLS]func_name{...}
  - Gemma 4:  <|tool_call>call:func_name\n{...}\n<tool_call|>
  - 通用 JSON 兜底

处理流水线:
  1. 根据模型类型选择对应 ToolCallExtractor 提取 raw tool calls
  2. JSON Schema 校验函数名 + 参数
  3. tool_choice 语义执行
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .base import ToolCallResult

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# 抽象提取器基类 + 注册表
# ═════════════════════════════════════════════════════════════════════

# 用于在 tool call 提取前去除 <think> 标签（防止推理内容干扰解析）
_THINK_FULL_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_IMPLICIT_RE = re.compile(r"^.*?</think>", re.DOTALL)


def _strip_think_tags(text: str) -> str:
    """去除 <think>...</think> 标签，支持完整和隐式两种模式。"""
    result = _THINK_FULL_RE.sub("", text)
    if result == text and "</think>" in text:
        result = _THINK_IMPLICIT_RE.sub("", text)
    return result.strip()


@dataclass
class ExtractedToolCalls:
    """提取器返回的原始 tool call 信息。"""
    found: bool = False
    calls: list[dict[str, Any]] = field(default_factory=list)  # [{"name":..., "arguments":...}]
    content: str | None = None  # tool call 之外的文本内容


class ToolCallExtractor(ABC):
    """Tool call 格式提取器抽象基类。"""

    @abstractmethod
    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        """从模型输出文本中提取 tool calls。"""


# 注册表
_EXTRACTOR_REGISTRY: dict[str, type[ToolCallExtractor]] = {}


def register_extractor(names: str | list[str], cls: type[ToolCallExtractor]) -> None:
    """注册 tool call 提取器。"""
    if isinstance(names, str):
        names = [names]
    for name in names:
        _EXTRACTOR_REGISTRY[name] = cls


def get_extractor(name: str) -> ToolCallExtractor:
    """根据名称创建提取器实例。"""
    cls = _EXTRACTOR_REGISTRY.get(name)
    if cls is None:
        available = list(_EXTRACTOR_REGISTRY.keys())
        raise KeyError(f"tool call extractor '{name}' not found, available: {available}")
    return cls()


def list_extractors() -> list[str]:
    """列出所有已注册的提取器名称。"""
    return sorted(_EXTRACTOR_REGISTRY.keys())


def _generate_tool_id() -> str:
    """生成唯一 tool call ID。"""
    return f"call_{uuid.uuid4().hex[:24]}"


# ═════════════════════════════════════════════════════════════════════
# GLM 4.7 提取器
# ═════════════════════════════════════════════════════════════════════


class Glm47Extractor(ToolCallExtractor):
    """GLM 4.7 tool call 提取器。

    格式:
        <tool_call>function_name
        <arg_key>param1</arg_key><arg_value>value1</arg_value>
        <arg_key>param2</arg_key><arg_value>value2</arg_value>
        </tool_call>
    """

    _FUNC_DETAIL_RE = re.compile(
        r"<tool_call>\s*([^\n<]+?)(?:\n|\s*)(<arg_key>.*?)?</tool_call>", re.DOTALL,
    )
    _ARG_RE = re.compile(
        r"<arg_key>\s*(.*?)\s*</arg_key>\s*<arg_value>(.*?)</arg_value>", re.DOTALL,
    )

    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        cleaned = _strip_think_tags(text)
        valid_names = self._get_tool_names(tools)
        matches = self._FUNC_DETAIL_RE.findall(cleaned)

        calls: list[dict] = []
        for match in matches:
            func_name = match[0].strip() if match[0] else ""
            args_section = match[1] if len(match) > 1 and match[1] else ""

            if not func_name:
                continue
            # 校验函数名
            if valid_names and func_name not in valid_names:
                continue

            arguments: dict[str, Any] = {}
            if args_section:
                for am in self._ARG_RE.finditer(args_section):
                    key = am.group(1).strip()
                    value = self._deserialize(am.group(2))
                    if key:
                        arguments[key] = value

            calls.append({"name": func_name, "arguments": arguments})

        if calls:
            return ExtractedToolCalls(found=True, calls=calls, content=None)

        return ExtractedToolCalls(found=False, content=cleaned)

    @staticmethod
    def _deserialize(value: str) -> Any:
        """尝试将字符串值解析为原生 JSON 类型。"""
        value = value.strip()
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value

    @staticmethod
    def _get_tool_names(tools: list[dict] | None) -> set[str]:
        if not tools:
            return set()
        return {
            t.get("function", {}).get("name", "")
            for t in tools
            if isinstance(t, dict)
        }


register_extractor(["glm47", "glm4", "glm"], Glm47Extractor)


# ═════════════════════════════════════════════════════════════════════
# Kimi / Moonshot 提取器
# ═════════════════════════════════════════════════════════════════════


class KimiExtractor(ToolCallExtractor):
    """Kimi K2 / Moonshot tool call 提取器。

    格式:
        <|tool_calls_section_begin|>
        <|tool_call_begin|>functions.get_weather:0<|tool_call_argument_begin|>{"city":"北京"}<|tool_call_end|>
        <|tool_calls_section_end|>
    """

    _TOOL_CALL_RE = re.compile(
        r"<\|tool_call_begin\|>\s*(?P<func_id>[^<]+?)(?::\d+)?\s*"
        r"<\|tool_call_argument_begin\|>\s*(?P<args>.*?)\s*<\|tool_call_end\|>",
        re.DOTALL,
    )

    def _has_tool_section(self, text: str) -> bool:
        return (
            "<|tool_calls_section_begin|>" in text
            or "<|tool_call_section_begin|>" in text
            or "<|tool_call_begin|>" in text
        )

    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        if not self._has_tool_section(text):
            return ExtractedToolCalls(found=False, content=text)

        calls: list[dict] = []
        # 提取 tool_call 区域之前的文本作为 content
        content = None
        for marker in ("<|tool_calls_section_begin|>", "<|tool_call_section_begin|>"):
            if marker in text:
                idx = text.find(marker)
                content = text[:idx].strip() if idx > 0 else None
                break

        for match in self._TOOL_CALL_RE.finditer(text):
            func_id = match.group("func_id").strip()
            func_args = match.group("args").strip()
            # func_id 格式: functions.get_weather:0 或 get_weather:0 或 get_weather
            func_name = func_id.split(":")[-2] if ":" in func_id else func_id
            func_name = func_name.split(".")[-1]  # 去除 "functions." 前缀

            try:
                args = json.loads(func_args)
            except json.JSONDecodeError:
                args = func_args

            calls.append({"name": func_name, "arguments": args if isinstance(args, dict) else {}})

        if calls:
            return ExtractedToolCalls(found=True, calls=calls, content=content)

        return ExtractedToolCalls(found=False, content=text)


register_extractor(["kimi", "kimi_k2", "moonshot"], KimiExtractor)


# ═════════════════════════════════════════════════════════════════════
# DeepSeek 提取器
# ═════════════════════════════════════════════════════════════════════


class DeepSeekExtractor(ToolCallExtractor):
    """DeepSeek V3/R1 tool call 提取器。

    格式（Unicode 特殊 token）:
        <｜tool▁calls▁begin｜>
        <｜tool▁call▁begin｜>function<｜tool▁sep｜>get_weather
        ```json
        {"city": "Paris"}
        ```<｜tool▁call▁end｜>
        <｜tool▁calls▁end｜>
    """

    TOOL_CALLS_START = "<｜tool▁calls▁begin｜>"
    TOOL_CALL_RE = re.compile(
        r"<｜tool▁call▁begin｜>(?:.*?)<｜tool▁sep｜>(?P<name>.*?)\n```json\n(?P<args>.*?)\n```<｜tool▁call▁end｜>",
        re.DOTALL,
    )
    # 简单模式（无 type 字段）
    TOOL_CALL_SIMPLE_RE = re.compile(
        r"<｜tool▁call▁begin｜>(?P<name>.*?)\n```json\n(?P<args>.*?)\n```<｜tool▁call▁end｜>",
        re.DOTALL,
    )

    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        if self.TOOL_CALLS_START not in text:
            return ExtractedToolCalls(found=False, content=text)

        # 提取 tool_call 区域前的文本
        content_end = text.find(self.TOOL_CALLS_START)
        content = text[:content_end].strip() if content_end > 0 else None

        calls: list[dict] = []
        # 先尝试带 type 字段的完整模式
        for match in self.TOOL_CALL_RE.finditer(text):
            name = match.group("name").strip()
            args_str = match.group("args").strip()
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = args_str
            calls.append({"name": name, "arguments": args if isinstance(args, dict) else {}})

        # 再尝试简单模式
        if not calls:
            for match in self.TOOL_CALL_SIMPLE_RE.finditer(text):
                name = match.group("name").strip()
                args_str = match.group("args").strip()
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = args_str
                calls.append({"name": name, "arguments": args if isinstance(args, dict) else {}})

        if calls:
            return ExtractedToolCalls(found=True, calls=calls, content=content)

        return ExtractedToolCalls(found=False, content=text)


register_extractor(["deepseek", "deepseek_v3", "deepseek_r1"], DeepSeekExtractor)


# ═════════════════════════════════════════════════════════════════════
# Qwen 提取器
# ═════════════════════════════════════════════════════════════════════


class QwenExtractor(ToolCallExtractor):
    """Qwen/Qwen3 tool call 提取器。

    格式:
        - XML: <tool_call>{"name": "func", "arguments": {...}}</tool_call>
        - Bracket: [Calling tool: func_name({"arg": "value"})]
    """

    _XML_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
    _BRACKET_RE = re.compile(r"\[Calling tool:\s*(\w+)\((\{.*?\})\)\]", re.DOTALL)

    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        cleaned = _strip_think_tags(text)
        calls: list[dict] = []

        # 先尝试 bracket 格式（Qwen3 风格）
        for name, args_str in self._BRACKET_RE.findall(cleaned):
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
            calls.append({"name": name.strip(), "arguments": args if isinstance(args, dict) else {}})

        if calls:
            remaining = self._BRACKET_RE.sub("", cleaned).strip()
            return ExtractedToolCalls(found=True, calls=calls, content=remaining or None)

        # 再尝试 XML 格式
        for match_str in self._XML_RE.findall(cleaned):
            try:
                data = json.loads(match_str)
                name = data.get("name", "")
                args = data.get("arguments", {})
                if name:
                    calls.append({"name": name, "arguments": args if isinstance(args, dict) else {}})
            except json.JSONDecodeError:
                continue

        if calls:
            remaining = self._XML_RE.sub("", cleaned).strip()
            return ExtractedToolCalls(found=True, calls=calls, content=remaining or None)

        return ExtractedToolCalls(found=False, content=cleaned)


register_extractor(["qwen", "qwen3"], QwenExtractor)


# ═════════════════════════════════════════════════════════════════════
# Hermes 提取器
# ═════════════════════════════════════════════════════════════════════


class HermesExtractor(ToolCallExtractor):
    """Hermes/NousResearch tool call 提取器，支持多层回退。

    格式优先级:
      1. <tool_call>{"name":..., "arguments":...}</tool_call>
      2. <function=name>...</function>（Nemotron / bare function）
      3. 裸 JSON {"name":..., "arguments":...}
    """

    _XML_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
    _FUNCTION_RE = re.compile(r"<function=([^>]+)>(\{.*?\})</function>", re.DOTALL)
    _RAW_JSON_RE = re.compile(
        r'\{"name":\s*"([^"]+)",\s*"arguments":\s*(\{[^}]*\})\}', re.DOTALL,
    )

    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        cleaned = _strip_think_tags(text)
        calls: list[dict] = []

        # Layer 1: 标准 XML
        for match_str in self._XML_RE.findall(cleaned):
            try:
                data = json.loads(match_str)
                name = data.get("name", "")
                args = data.get("arguments", {})
                if name:
                    calls.append({"name": name, "arguments": args if isinstance(args, dict) else {}})
            except json.JSONDecodeError:
                continue

        if calls:
            remaining = self._XML_RE.sub("", cleaned).strip()
            return ExtractedToolCalls(found=True, calls=calls, content=remaining or None)

        # Layer 2: <function=name>{...}</function>
        for name, args_str in self._FUNCTION_RE.findall(cleaned):
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
            calls.append({"name": name.strip(), "arguments": args if isinstance(args, dict) else {}})

        if calls:
            remaining = self._FUNCTION_RE.sub("", cleaned).strip()
            return ExtractedToolCalls(found=True, calls=calls, content=remaining or None)

        # Layer 3: 裸 JSON（仅第一个，防止误匹配）
        raw_matches = self._RAW_JSON_RE.findall(cleaned)
        if raw_matches:
            name, args_str = raw_matches[0]
            try:
                args = json.loads(args_str)
                # 验证工具名合法性
                valid = True
                if tools:
                    tool_names = [t.get("function", {}).get("name", "") for t in tools if isinstance(t, dict)]
                    valid = name in tool_names
                if valid and name:
                    calls.append({"name": name, "arguments": args if isinstance(args, dict) else {}})
            except json.JSONDecodeError:
                pass

        if calls:
            remaining = self._RAW_JSON_RE.sub("", cleaned, count=1).strip()
            return ExtractedToolCalls(found=True, calls=calls, content=remaining or None)

        return ExtractedToolCalls(found=False, content=cleaned)


register_extractor(["hermes", "nous", "qwen3_coder"], HermesExtractor)


# ═════════════════════════════════════════════════════════════════════
# Llama 提取器
# ═════════════════════════════════════════════════════════════════════


class LlamaExtractor(ToolCallExtractor):
    """Llama tool call 提取器。

    格式: <function=name>{"arg": "value"}</function>
    """

    _FUNCTION_RE = re.compile(r"<function=([^>]+)>(\{.*?\})</function>", re.DOTALL)

    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        calls: list[dict] = []
        for name, args_str in self._FUNCTION_RE.findall(text):
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
            calls.append({"name": name.strip(), "arguments": args if isinstance(args, dict) else {}})

        if calls:
            remaining = self._FUNCTION_RE.sub("", text).strip()
            return ExtractedToolCalls(found=True, calls=calls, content=remaining or None)

        return ExtractedToolCalls(found=False, content=text)


register_extractor(["llama", "llama3", "llama4"], LlamaExtractor)


# ═════════════════════════════════════════════════════════════════════
# Mistral 提取器
# ═════════════════════════════════════════════════════════════════════


class MistralExtractor(ToolCallExtractor):
    """Mistral tool call 提取器。

    格式:
      - 旧版: [TOOL_CALLS] [{"name": "func", "arguments": {...}}]
      - 新版: [TOOL_CALLS]func_name{"arg": "value"}
    """

    BOT_TOKEN = "[TOOL_CALLS]"

    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        if self.BOT_TOKEN not in text:
            return ExtractedToolCalls(found=False, content=text)

        parts = text.split(self.BOT_TOKEN)
        content = parts[0].strip() or None
        calls: list[dict] = []

        for raw in parts[1:]:
            raw = raw.strip()
            if not raw:
                continue

            # 新格式: func_name{"arg": "value"}
            if not raw.startswith("[") and "{" in raw:
                end_name = raw.find("{")
                name = raw[:end_name].strip()
                args_str = raw[end_name:]
                if name:
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {}
                    calls.append({"name": name, "arguments": args if isinstance(args, dict) else {}})
                continue

            # 旧格式: [{"name": "func", "arguments": {...}}]
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "name" in item:
                            args = item.get("arguments", {})
                            calls.append({
                                "name": item["name"],
                                "arguments": args if isinstance(args, dict) else {},
                            })
            except json.JSONDecodeError:
                pass

        if calls:
            return ExtractedToolCalls(found=True, calls=calls, content=content)

        return ExtractedToolCalls(found=False, content=text)


register_extractor("mistral", MistralExtractor)


# ═════════════════════════════════════════════════════════════════════
# Gemma 4 提取器
# ═════════════════════════════════════════════════════════════════════


class Gemma4Extractor(ToolCallExtractor):
    """Gemma 4 tool call extractor.

    Official format (https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4):
        <|tool_call>
        call: function_name
        {"arg1": "value1", "arg2": "value2"}
        <tool_call|>

    Multiple tool calls are emitted as consecutive blocks.
    The <|"|> quoting syntax used in tool responses is NOT expected in
    model output — the model always produces plain JSON arguments.
    """

    # Match a single tool_call block.
    # Group 1: function name after "call:"
    # Group 2: JSON arguments body (everything between name line and closing tag)
    _BLOCK_RE = re.compile(
        r"<\|tool_call>\s*"
        r"call:\s*(?P<name>[^\n]+?)\s*\n"
        r"(?P<args>.*?)"
        r"\s*<tool_call\|>",
        re.DOTALL,
    )

    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        cleaned = _strip_think_tags(text)

        if "<|tool_call>" not in cleaned:
            return ExtractedToolCalls(found=False, content=cleaned)

        # Extract content before the first tool_call block
        first_pos = cleaned.find("<|tool_call>")
        content = cleaned[:first_pos].strip() if first_pos > 0 else None

        calls: list[dict] = []
        for match in self._BLOCK_RE.finditer(cleaned):
            func_name = match.group("name").strip()
            args_str = match.group("args").strip()

            if not func_name:
                continue

            # Parse JSON arguments
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                logger.warning(
                    "gemma4 tool_call JSON parse failed for func=%s, raw=%s",
                    func_name, args_str[:200],
                )
                args = {}

            calls.append({
                "name": func_name,
                "arguments": args if isinstance(args, dict) else {},
            })

        if calls:
            logger.debug("gemma4 extractor found %d tool call(s)", len(calls))
            return ExtractedToolCalls(found=True, calls=calls, content=content)

        return ExtractedToolCalls(found=False, content=cleaned)


register_extractor(["gemma4", "gemma"], Gemma4Extractor)


# ═════════════════════════════════════════════════════════════════════
# 通用 JSON 兜底提取器（Auto）
# ═════════════════════════════════════════════════════════════════════


class AutoExtractor(ToolCallExtractor):
    """自动检测 tool call 格式的通用提取器。

    按优先级依次尝试所有已知格式:
      Mistral → Qwen → DeepSeek → GLM → Kimi → Hermes → Llama → 裸 JSON
    """

    # 按优先级排列的提取器类型
    _TRY_ORDER = [
        "mistral", "deepseek", "gemma4", "glm47", "kimi", "qwen", "hermes", "llama",
    ]

    def extract(self, text: str, tools: list[dict] | None = None) -> ExtractedToolCalls:
        for name in self._TRY_ORDER:
            try:
                extractor = get_extractor(name)
                result = extractor.extract(text, tools)
                if result.found:
                    logger.info("auto-detected tool call format: %s", name)
                    return result
            except KeyError:
                continue

        # 最后兜底: 从文本中提取平衡花括号的 JSON 对象
        return self._extract_raw_json(text)

    def _extract_raw_json(self, text: str) -> ExtractedToolCalls:
        """兜底: 从文本中提取含 "name" 字段的 JSON 对象。"""
        cleaned = _strip_think_tags(text)
        calls: list[dict] = []
        depth = 0
        start = None

        for i, ch in enumerate(cleaned):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    depth = 0
                    start = None
                    continue
                if depth == 0 and start is not None:
                    json_str = cleaned[start : i + 1]
                    try:
                        obj = json.loads(json_str)
                        if isinstance(obj, dict) and "name" in obj:
                            args = obj.get("arguments", {})
                            calls.append({
                                "name": obj["name"],
                                "arguments": args if isinstance(args, dict) else {},
                            })
                    except json.JSONDecodeError:
                        pass
                    start = None

        if calls:
            return ExtractedToolCalls(found=True, calls=calls, content=None)

        return ExtractedToolCalls(found=False, content=cleaned)


register_extractor(["auto", "generic"], AutoExtractor)


# ═════════════════════════════════════════════════════════════════════
# 模型类型检测
# ═════════════════════════════════════════════════════════════════════


def detect_model_type(model_name: str) -> str:
    """根据模型名称推断 tool call 提取器类型。

    Returns:
        注册表中的提取器名称（如 "glm47", "kimi", "deepseek", "qwen", "hermes" 等），
        或空字符串表示使用 "auto" 自动检测。
    """
    name_lower = model_name.lower()

    if "glm" in name_lower:
        return "glm47"
    if "kimi" in name_lower or "moonshot" in name_lower:
        return "kimi"
    if "deepseek" in name_lower:
        return "deepseek"
    if "qwen3" in name_lower and "coder" in name_lower:
        return "hermes"  # Qwen3-Coder 使用 hermes 格式
    if "qwen" in name_lower:
        return "qwen"
    if "hermes" in name_lower or "nous" in name_lower:
        return "hermes"
    if "llama" in name_lower:
        return "llama"
    if "mistral" in name_lower or "devstral" in name_lower:
        return "mistral"
    if "gemma" in name_lower:
        # Gemma 4 has a dedicated tool call format: <|tool_call>call:...<tool_call|>
        if "gemma4" in name_lower or "gemma-4" in name_lower:
            return "gemma4"
        # Gemma 3 does not define a specific FC format; use auto fallback.
        return ""

    return ""


# ═════════════════════════════════════════════════════════════════════
# 数据结构
# ═════════════════════════════════════════════════════════════════════


@dataclass
class ToolCallMetrics:
    """Function Call 处理指标。"""
    tool_call_count: int = 0
    tool_call_success: bool = True
    tool_call_retried: bool = False
    tool_call_parse_ms: int = 0


@dataclass
class ToolCallParseResult:
    """解析结果，包含 tool calls + 剩余文本 + 指标。"""
    calls: list[ToolCallResult] | None = None
    remaining_text: str = ""
    metrics: ToolCallMetrics = field(default_factory=ToolCallMetrics)


# ═════════════════════════════════════════════════════════════════════
# 统一解析器
# ═════════════════════════════════════════════════════════════════════


class ToolCallParser:
    """统一 Function Call 解析器 — 三引擎共用。

    流水线:
      1. 选择对应 ToolCallExtractor 提取 raw tool calls
      2. JSON Schema 校验参数
      3. tool_choice 语义执行
    """

    def __init__(self) -> None:
        self._validator_cache: dict[str, Any] = {}

    # ─── 主入口 ───

    def parse(
        self,
        text: str,
        tools: list[dict] | None,
        tool_choice: str = "auto",
        model_type: str = "",
    ) -> ToolCallParseResult:
        """完整解析流水线。

        Args:
            text: 模型生成的原始文本。
            tools: 工具定义列表（OpenAI tools 格式）。
            tool_choice: "none" / "auto" / "required" / 具体函数名。
            model_type: 模型类型（注册表名称），空字符串使用 auto 提取器。
        """
        start_ms = _now_ms()
        metrics = ToolCallMetrics()

        if tool_choice == "none" or not tools:
            return ToolCallParseResult(
                remaining_text=text,
                metrics=ToolCallMetrics(tool_call_parse_ms=_elapsed_ms(start_ms)),
            )

        # 第一层: 选择提取器并提取
        extractor_name = model_type if model_type and model_type in _EXTRACTOR_REGISTRY else "auto"
        extractor = get_extractor(extractor_name)
        extracted = extractor.extract(text, tools)

        if not extracted.found:
            metrics.tool_call_parse_ms = _elapsed_ms(start_ms)
            if tool_choice == "required":
                metrics.tool_call_success = False
                logger.warning("tool_choice=required but no tool_call detected")
            return ToolCallParseResult(
                calls=None,
                remaining_text=extracted.content or text,
                metrics=metrics,
            )

        # 第二层: 校验并转换
        calls: list[ToolCallResult] = []
        all_valid = True
        for raw_call in extracted.calls:
            tc, valid, err = self._validate_and_convert(raw_call, tools)
            if tc:
                calls.append(tc)
            if not valid:
                all_valid = False
                logger.warning("tool_call validation failed: %s | raw=%s", err, raw_call)

        # 第三层: tool_choice 语义
        calls = self._enforce_tool_choice(calls, tool_choice)

        metrics.tool_call_count = len(calls) if calls else 0
        metrics.tool_call_success = all_valid and (calls is not None)
        metrics.tool_call_parse_ms = _elapsed_ms(start_ms)

        if tool_choice == "required" and not calls:
            metrics.tool_call_success = False

        return ToolCallParseResult(
            calls=calls or None,
            remaining_text=extracted.content or "",
            metrics=metrics,
        )

    # ─── 校验 + 转换 ───

    def _validate_and_convert(
        self,
        raw_call: dict,
        tools: list[dict],
    ) -> tuple[ToolCallResult | None, bool, str]:
        """校验单个 tool call 并转换为 ToolCallResult。"""
        name = raw_call.get("name", "")
        arguments = raw_call.get("arguments", {})

        if not name:
            return None, False, "missing function name"

        # 查找工具 schema
        tool_schema = self._find_tool_schema(name, tools)
        if tool_schema is None:
            return None, False, f"unknown function: {name}"

        # arguments 可能是 dict 或 str
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}

        # JSON Schema 校验
        valid, err = self._validate_arguments(arguments, tool_schema)

        tc = ToolCallResult(
            id=_generate_tool_id(),
            function_name=name,
            function_arguments=json.dumps(arguments, ensure_ascii=False) if isinstance(arguments, dict) else str(arguments),
        )
        return tc, valid or True, err  # 即使校验失败也返回 result，只报 warning

    def _find_tool_schema(self, name: str, tools: list[dict]) -> dict | None:
        """在 tools 列表中查找指定函数名的 schema。"""
        for tool in tools:
            func = tool.get("function", {})
            if func.get("name") == name:
                return func
        return None

    def _validate_arguments(self, arguments: dict, tool_schema: dict) -> tuple[bool, str]:
        """使用 jsonschema 校验 arguments。"""
        params_schema = tool_schema.get("parameters")
        if not params_schema:
            return True, ""

        if isinstance(params_schema, str):
            try:
                params_schema = json.loads(params_schema)
            except json.JSONDecodeError:
                return True, ""

        if not isinstance(params_schema, dict):
            return True, ""

        try:
            import jsonschema
        except ImportError:
            return True, ""

        schema_key = self._compute_schema_hash(params_schema)
        validator = self._validator_cache.get(schema_key)
        if validator is None:
            try:
                validator_cls = jsonschema.validators.validator_for(params_schema)
                validator = validator_cls(params_schema)
                self._validator_cache[schema_key] = validator
            except Exception:
                return True, ""

        errors = list(validator.iter_errors(arguments))
        if errors:
            err_msgs = "; ".join(e.message for e in errors[:3])
            return False, f"schema validation failed: {err_msgs}"
        return True, ""

    # ─── tool_choice 语义 ───

    def _enforce_tool_choice(
        self,
        calls: list[ToolCallResult],
        tool_choice: str,
    ) -> list[ToolCallResult] | None:
        """根据 tool_choice 过滤 tool calls。"""
        if tool_choice == "none":
            return None
        if tool_choice in ("auto", "required"):
            return calls if calls else None
        # 具体函数名
        filtered = [c for c in calls if c.function_name == tool_choice]
        return filtered if filtered else None

    # ─── 后校验（供 llamacpp 等已有 tool 解析的引擎使用）───

    def validate_existing_calls(
        self,
        calls: list[ToolCallResult],
        tools: list[dict],
    ) -> ToolCallMetrics:
        """对已提取的 tool calls 做 schema 后校验。"""
        start_ms = _now_ms()
        metrics = ToolCallMetrics(tool_call_count=len(calls))
        all_valid = True

        for tc in calls:
            try:
                args = json.loads(tc.function_arguments) if tc.function_arguments else {}
            except json.JSONDecodeError:
                all_valid = False
                continue

            tool_schema = self._find_tool_schema(tc.function_name, tools)
            if tool_schema is None:
                all_valid = False
                continue

            valid, _ = self._validate_arguments(args, tool_schema)
            if not valid:
                all_valid = False

        metrics.tool_call_success = all_valid
        metrics.tool_call_parse_ms = _elapsed_ms(start_ms)
        return metrics

    # ─── 工具方法 ───

    @staticmethod
    def build_tool_call_json_schema(tools: list[dict]) -> dict:
        """从 tools 列表构建 union JSON Schema（anyOf 格式）。"""
        func_names: list[str] = []
        arg_schemas: list[dict] = []

        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "")
            if not name:
                continue
            func_names.append(name)
            params = func.get("parameters", {})
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except json.JSONDecodeError:
                    params = {"type": "object"}
            if not isinstance(params, dict):
                params = {"type": "object"}
            arg_schemas.append(params)

        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "enum": func_names} if func_names else {"type": "string"},
                "arguments": (
                    {"anyOf": arg_schemas} if len(arg_schemas) > 1
                    else (arg_schemas[0] if arg_schemas else {"type": "object"})
                ),
            },
            "required": ["name", "arguments"],
        }

    @staticmethod
    def tools_to_dict_list(tools: list[Any]) -> list[dict]:
        """将 ToolDef 列表转为 dict 列表。"""
        result = []
        for t in tools:
            if isinstance(t, dict):
                result.append(t)
            elif hasattr(t, "function") and t.function:
                func = t.function
                params = func.parameters if hasattr(func, "parameters") else "{}"
                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except json.JSONDecodeError:
                        params = {}
                result.append({
                    "type": "function",
                    "function": {
                        "name": func.name,
                        "description": getattr(func, "description", ""),
                        "parameters": params,
                    },
                })
        return result

    @staticmethod
    def _compute_schema_hash(schema: dict) -> str:
        raw = json.dumps(schema, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(raw.encode()).hexdigest()


# ─────────── 辅助函数 ───────────


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _elapsed_ms(start_ms: int) -> int:
    return int(time.monotonic() * 1000) - start_ms
