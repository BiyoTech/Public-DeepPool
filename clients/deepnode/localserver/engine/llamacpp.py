"""llama.cpp 推理引擎 — 适用于 Mac Intel 或低版本 macOS（< 13.5）。

通过 llama-cpp-python 加载 GGUF 格式量化模型，
支持 Chat Completions 语义（非流式 + 流式）。

安装: pip install llama-cpp-python
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Generator

from .base import (
    ChatChoice,
    ChatCompletionChunkResult,
    ChatCompletionRequest,
    ChatCompletionResult,
    ChatMessage,
    ChoiceLogprobs,
    LLMEngine,
    StreamChoice,
    StreamDelta,
    TokenLogprobItem,
    ToolCallResult,
    TopLogprobItem,
    UsageStats,
)
from .tool_call_parser import ToolCallMetrics, ToolCallParser, detect_model_type

logger = logging.getLogger(__name__)


def _messages_to_llama_format(messages: list[ChatMessage]) -> list[dict]:
    """将 ChatMessage 列表转换为 llama-cpp-python 的 messages 格式。"""
    result = []
    for m in messages:
        msg: dict[str, Any] = {"role": m.role}
        if m.content is not None:
            msg["content"] = m.content
        if m.name:
            msg["name"] = m.name
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function_name,
                        "arguments": tc.function_arguments,
                    },
                }
                for tc in m.tool_calls
            ]
        result.append(msg)
    return result


def _build_create_kwargs(request: ChatCompletionRequest) -> dict:
    """从 ChatCompletionRequest 构建 llama-cpp-python create_chat_completion 参数。"""
    kwargs: dict[str, Any] = {
        "messages": _messages_to_llama_format(request.messages),
        "temperature": request.temperature,
        "top_p": request.top_p,
        "max_tokens": request.max_tokens,
    }
    if request.n > 1:
        kwargs["n"] = request.n  # llama-cpp-python 部分版本不支持，但传入无害
    if request.stop:
        kwargs["stop"] = request.stop
    if request.presence_penalty:
        kwargs["presence_penalty"] = request.presence_penalty
    if request.frequency_penalty:
        kwargs["frequency_penalty"] = request.frequency_penalty
    if request.seed is not None:
        kwargs["seed"] = request.seed
    if request.logprobs:
        kwargs["logprobs"] = True
        if request.top_logprobs is not None:
            kwargs["top_logprobs"] = request.top_logprobs
    if request.response_format and request.response_format.type != "text":
        kwargs["response_format"] = {"type": request.response_format.type}
    if request.tools:
        kwargs["tools"] = [
            {
                "type": t.type,
                "function": {
                    "name": t.function.name,
                    "description": t.function.description or "",
                    "parameters": t.function.parameters,
                },
            }
            for t in request.tools
            if t.function
        ]
        kwargs["tool_choice"] = request.tool_choice or "auto"
    return kwargs


def _parse_logprobs(raw_logprobs: dict | None) -> ChoiceLogprobs | None:
    """解析 llama-cpp-python 返回的 logprobs 字段。"""
    if not raw_logprobs:
        return None
    content_items = []
    for item in raw_logprobs.get("content", []):
        top_lps = [
            TopLogprobItem(token=t.get("token", ""), logprob=t.get("logprob", 0.0))
            for t in item.get("top_logprobs", [])
        ]
        content_items.append(
            TokenLogprobItem(
                token=item.get("token", ""),
                logprob=item.get("logprob", 0.0),
                top_logprobs=top_lps,
            )
        )
    return ChoiceLogprobs(content=content_items) if content_items else None


class LlamaCppEngine(LLMEngine):
    """基于 llama-cpp-python 的推理引擎，支持 Chat Completions 语义。

    适用于 macOS Intel / 低版本 macOS（< 13.5）。
    EngineConfig 中的 max_kv_size 映射为 n_ctx（上下文长度），
    tokenizer 由 llama.cpp 内部管理，不使用外部线程池。
    """

    def __init__(
        self,
        n_gpu_layers: int = -1,
        n_ctx: int = 4096,
        engine_config: "EngineConfig | None" = None,
    ) -> None:
        from config import EngineConfig

        self._engine_config = engine_config or EngineConfig()
        self._lock = threading.Lock()
        self._llm: Any | None = None
        self._model_name: str = ""
        self._n_gpu_layers = n_gpu_layers
        self._n_ctx = n_ctx
        self._model_type: str = ""
        self._tc_parser = ToolCallParser()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def ready(self) -> bool:
        return self._llm is not None

    def unload(self) -> None:
        """卸载 llama.cpp 模型并释放资源。"""
        with self._lock:
            if self._llm is None:
                return
            logger.info("unloading llamacpp model name=%s", self._model_name)
            self._llm = None
            self._model_name = ""
            self._model_type = ""
            import gc
            gc.collect()
            logger.info("llamacpp model unloaded")

    def load(self, model_name: str, model_path: Path) -> None:
        with self._lock:
            if self._llm is not None and self._model_name == model_name:
                return
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise RuntimeError(
                    "llama-cpp-python is not installed. "
                    "Install with: pip install llama-cpp-python"
                ) from exc

            model_file = self._resolve_gguf(model_path)
            logger.info(
                "loading llama.cpp model name=%s path=%s n_gpu_layers=%d n_ctx=%d",
                model_name, model_file, self._n_gpu_layers, self._n_ctx,
            )
            self._llm = Llama(
                model_path=str(model_file),
                n_gpu_layers=self._n_gpu_layers,
                n_ctx=self._n_ctx,
                verbose=False,
                chat_format="chatml",
            )
            self._model_name = model_name
            self._model_type = detect_model_type(model_name)
            logger.info("llama.cpp model loaded name=%s model_type=%s", model_name, self._model_type or "standard")

    def chat_complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        """非流式 Chat Completions。"""
        with self._lock:
            if self._llm is None:
                raise RuntimeError("model engine is not ready")

            kwargs = _build_create_kwargs(request)
            kwargs["stream"] = False
            output = self._llm.create_chat_completion(**kwargs)

        # 解析 choices
        choices = []
        for i, c in enumerate(output.get("choices", [])):
            msg_data = c.get("message", {})
            tool_calls = None
            if msg_data.get("tool_calls"):
                tool_calls = [
                    ToolCallResult(
                        id=tc.get("id", ""),
                        type=tc.get("type", "function"),
                        function_name=tc.get("function", {}).get("name", ""),
                        function_arguments=tc.get("function", {}).get("arguments", ""),
                    )
                    for tc in msg_data["tool_calls"]
                ]
            choices.append(
                ChatChoice(
                    index=c.get("index", i),
                    message=ChatMessage(
                        role=msg_data.get("role", "assistant"),
                        content=msg_data.get("content"),
                        tool_calls=tool_calls,
                    ),
                    finish_reason=c.get("finish_reason", "stop"),
                    logprobs=_parse_logprobs(c.get("logprobs")),
                )
            )

        usage_data = output.get("usage", {})
        usage = UsageStats(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        # ToolCallParser schema 后校验 + 指标收集
        tc_metrics: ToolCallMetrics | None = None
        for c in choices:
            if c.message and c.message.tool_calls:
                dict_tools = ToolCallParser.tools_to_dict_list(request.tools) if request.tools else []
                tc_metrics = self._tc_parser.validate_existing_calls(c.message.tool_calls, dict_tools)
                break

        return ChatCompletionResult(choices=choices, usage=usage, tool_call_metrics=tc_metrics)

    def stream_chat_complete(
        self, request: ChatCompletionRequest,
    ) -> Generator[ChatCompletionChunkResult, None, None]:
        """流式 Chat Completions，逐 chunk yield。"""
        with self._lock:
            if self._llm is None:
                raise RuntimeError("model engine is not ready")

            kwargs = _build_create_kwargs(request)
            kwargs["stream"] = True
            stream = self._llm.create_chat_completion(**kwargs)

        for chunk in stream:
            chunk_choices = []
            for c in chunk.get("choices", []):
                delta_data = c.get("delta", {})
                delta = StreamDelta(
                    role=delta_data.get("role"),
                    content=delta_data.get("content"),
                )
                chunk_choices.append(
                    StreamChoice(
                        index=c.get("index", 0),
                        delta=delta,
                        finish_reason=c.get("finish_reason"),
                        logprobs=_parse_logprobs(c.get("logprobs")),
                    )
                )
            yield ChatCompletionChunkResult(choices=chunk_choices)

    @staticmethod
    def _resolve_gguf(model_path: Path) -> Path:
        """定位 GGUF 模型文件：文件直接返回，目录则查找 .gguf 文件。"""
        if model_path.is_file():
            return model_path
        parent = model_path if model_path.is_dir() else model_path.parent
        gguf_files = sorted(parent.glob("*.gguf"))
        if gguf_files:
            return gguf_files[0]
        return model_path
