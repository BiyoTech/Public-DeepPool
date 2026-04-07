"""推理引擎模块 — 提供多后端推理能力的统一抽象（Chat Completions 语义）。"""

from .base import (
    ChatChoice,
    ChatCompletionChunkResult,
    ChatCompletionRequest,
    ChatCompletionResult,
    ChatMessage,
    ChoiceLogprobs,
    FunctionDef,
    LLMEngine,
    ResponseFormat,
    StreamChoice,
    StreamDelta,
    ToolCallResult,
    ToolDef,
    TopLogprobItem,
    TokenLogprobItem,
    UsageStats,
)
from .selector import detect_engine_type
from .tool_call_parser import ToolCallMetrics, ToolCallParseResult, ToolCallParser

__all__ = [
    "ChatChoice",
    "ChatCompletionChunkResult",
    "ChatCompletionRequest",
    "ChatCompletionResult",
    "ChatMessage",
    "ChoiceLogprobs",
    "FunctionDef",
    "LLMEngine",
    "ResponseFormat",
    "StreamChoice",
    "StreamDelta",
    "ToolCallResult",
    "ToolCallMetrics",
    "ToolCallParseResult",
    "ToolCallParser",
    "ToolDef",
    "TopLogprobItem",
    "TokenLogprobItem",
    "UsageStats",
    "detect_engine_type",
]
