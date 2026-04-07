"""推理引擎抽象基类 — 对齐 OpenAI Chat Completions 语义。

所有引擎实现需继承 LLMEngine，实现 chat_complete（非流式）
和 stream_chat_complete（流式）两个核心方法。

兼容 DeepSeek R1 (reasoning_content) / Qwen3 (<think>) 等推理模型。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator, Optional


# ─────────── 请求数据结构 ───────────

@dataclass
class ChatMessage:
    """单条聊天消息。"""
    role: str                              # system / user / assistant / tool
    content: Optional[str] = None
    name: Optional[str] = None             # role=tool 时标识函数名
    tool_calls: list[ToolCallResult] | None = None
    tool_call_id: Optional[str] = None     # role=tool 时关联的 tool_call id
    reasoning_content: Optional[str] = None  # 推理/思考内容（DeepSeek R1 / Qwen3）


@dataclass
class FunctionDef:
    """工具函数定义。"""
    name: str
    description: str = ""
    parameters: str = "{}"                 # JSON Schema 字符串


@dataclass
class ToolDef:
    """工具定义（type 固定 "function"）。"""
    type: str = "function"
    function: FunctionDef | None = None


@dataclass
class ResponseFormat:
    """响应格式控制。"""
    type: str = "text"                     # "text" / "json_object" / "json_schema"
    json_schema: Optional[str] = None


@dataclass
class ChatCompletionRequest:
    """Chat Completions 请求，对齐 OpenAI API 字段。"""
    messages: list[ChatMessage]
    temperature: float = 1.0
    top_p: float = 1.0
    n: int = 1
    max_tokens: int = 256
    stop: list[str] | None = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    tools: list[ToolDef] | None = None
    tool_choice: str = "auto"              # "none" / "auto" / "required" / 函数名
    response_format: ResponseFormat | None = None
    seed: int | None = None
    logprobs: bool = False
    top_logprobs: int | None = None
    user: str = ""
    request_id: str = ""
    enable_thinking: bool | None = None    # 是否启用思考模式


# ─────────── 响应数据结构 ───────────

@dataclass
class ToolCallResult:
    """引擎返回的工具调用结果。"""
    id: str = ""
    type: str = "function"
    function_name: str = ""
    function_arguments: str = ""           # JSON 字符串


@dataclass
class TopLogprobItem:
    """单个 top logprob 条目。"""
    token: str = ""
    logprob: float = 0.0
    bytes: list[int] | None = None


@dataclass
class TokenLogprobItem:
    """单个 token 的 logprob 信息。"""
    token: str = ""
    logprob: float = 0.0
    bytes: list[int] | None = None
    top_logprobs: list[TopLogprobItem] = field(default_factory=list)


@dataclass
class ChoiceLogprobs:
    """单个 choice 的 logprobs 列表。"""
    content: list[TokenLogprobItem] = field(default_factory=list)


@dataclass
class CompletionTokensDetails:
    """补全 token 的细分统计，对齐 OpenAI CompletionTokensDetails。"""
    reasoning_tokens: int = 0


@dataclass
class UsageStats:
    """Token 用量统计。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    completion_tokens_details: CompletionTokensDetails | None = None


@dataclass
class ChatChoice:
    """非流式：单个 choice 结果。"""
    index: int = 0
    message: ChatMessage | None = None
    finish_reason: str = "stop"            # stop / length / tool_calls / content_filter
    logprobs: ChoiceLogprobs | None = None


@dataclass
class ChatCompletionResult:
    """Non-streaming complete response."""
    choices: list[ChatChoice] = field(default_factory=list)
    usage: UsageStats = field(default_factory=UsageStats)
    tool_call_metrics: "ToolCallMetrics | None" = None  # FC parse metrics (lazy import)
    infer_metrics: Any = None  # InferMetrics from vllm_mlx engine (timing observability)


@dataclass
class StreamDelta:
    """Streaming delta fragment."""
    role: Optional[str] = None
    content: Optional[str] = None
    reasoning_content: Optional[str] = None  # Reasoning/thinking content delta
    tool_calls: list[ToolCallResult] | None = None


@dataclass
class StreamChoice:
    """Streaming single choice delta."""
    index: int = 0
    delta: StreamDelta | None = None
    finish_reason: Optional[str] = None
    logprobs: ChoiceLogprobs | None = None


@dataclass
class ChatCompletionChunkResult:
    """Streaming single chunk."""
    choices: list[StreamChoice] = field(default_factory=list)
    usage: UsageStats | None = None
    infer_metrics: Any = None  # InferMetrics from vllm_mlx engine (timing observability)


# ─────────── 引擎抽象 ───────────

class LLMEngine(abc.ABC):
    """推理引擎统一接口 — Chat Completions 语义。"""

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def ready(self) -> bool:
        ...

    @abc.abstractmethod
    def load(self, model_name: str, model_path: Path) -> None:
        """加载模型，model_path 指向模型文件或目录。"""
        ...

    def unload(self) -> None:
        """卸载模型并释放所有资源（GPU 显存、Metal 缓存等）。

        子类应覆盖此方法以执行引擎特定的清理逻辑。
        默认实现为空操作，保证调用安全。
        """

    @abc.abstractmethod
    def chat_complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        """非流式 Chat Completions。"""
        ...

    @abc.abstractmethod
    def stream_chat_complete(
        self, request: ChatCompletionRequest,
    ) -> Generator[ChatCompletionChunkResult, None, None]:
        """流式 Chat Completions，逐 chunk yield。"""
        ...
