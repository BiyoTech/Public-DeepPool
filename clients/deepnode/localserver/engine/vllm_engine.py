"""vLLM 推理引擎 — 仅适用于 Linux + NVIDIA GPU 环境。

支持 Chat Completions 语义（非流式 + 流式），基于 vLLM 的
SamplingParams 实现温度/top_p/stop/n/logprobs 等参数。

Function Call 通过 Outlines Guided Decoding（structured_outputs）
从 token 层面约束输出格式，后处理仍经 ToolCallParser schema 校验。

安装: pip install vllm
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any, Generator

from .base import (
    ChatChoice,
    ChatCompletionChunkResult,
    ChatCompletionRequest,
    ChatCompletionResult,
    ChatMessage,
    LLMEngine,
    StreamChoice,
    StreamDelta,
    ToolCallResult,
    UsageStats,
)
from .reasoning import ReasoningParser, detect_reasoning_parser
from .tool_call_parser import ToolCallMetrics, ToolCallParser, detect_model_type

logger = logging.getLogger(__name__)

# Default stop sequences per model family (passed to vLLM SamplingParams.stop)
# Gemma 3 (gemma3/gemma3n): <start_of_turn> / <end_of_turn>
# Gemma 4: <|turn> / <turn|> (new control tokens)
_MODEL_DEFAULT_STOP: dict[str, list[str]] = {
    "glm": ["<|user|>", "<|observation|>", "<|endoftext|>"],
    "qwen": ["<|im_end|>", "<|endoftext|>"],
    "deepseek": ["<|end▁of▁sentence|>"],
    "kimi": ["<|im_end|>", "<|endoftext|>"],
    "llama": ["<|eot_id|>"],
    "mistral": ["</s>"],
    "gemma3": ["<end_of_turn>", "<start_of_turn>"],
    "gemma4": ["<turn|>", "<|turn>", "<|tool_response>"],
}


def _get_default_stop(model_name: str) -> list[str]:
    """Return default stop sequences for the given model name."""
    name_lower = model_name.lower()
    # Gemma family: check gemma4 first to avoid gemma3 matching gemma4 names
    if "gemma" in name_lower:
        if "gemma4" in name_lower or "gemma-4" in name_lower:
            return _MODEL_DEFAULT_STOP["gemma4"]
        return _MODEL_DEFAULT_STOP["gemma3"]
    for key, stops in _MODEL_DEFAULT_STOP.items():
        if key in name_lower:
            return stops
    return []


class VLLMEngine(LLMEngine):
    """基于 vLLM 的推理引擎，支持 Chat Completions 语义。

    Linux NVIDIA GPU 环境，KV Cache 由 vLLM 库内部管理。
    Function Call 场景通过 structured_outputs 注入 JSON Schema 约束。
    """

    def __init__(self, engine_config: "EngineConfig | None" = None) -> None:
        from config import EngineConfig

        self._engine_config = engine_config or EngineConfig()
        self._lock = threading.Lock()
        self._llm: Any | None = None
        self._sampling_params_cls: Any | None = None
        self._model_name: str = ""
        self._tokenizer: Any | None = None
        self._structured_outputs_available: bool = False
        self._model_type: str = ""
        self._default_stop: list[str] = []
        self._reasoning_parser_name: str | None = None
        self._tc_parser = ToolCallParser()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def ready(self) -> bool:
        return self._llm is not None

    def unload(self) -> None:
        """卸载 vLLM 模型并释放 GPU 资源。"""
        with self._lock:
            if self._llm is None:
                return
            logger.info("unloading vllm model name=%s", self._model_name)
            self._llm = None
            self._tokenizer = None
            self._model_name = ""
            self._model_type = ""
            self._default_stop = []
            self._reasoning_parser_name = None
            import gc
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            logger.info("vllm model unloaded, GPU cache cleared")

    def load(self, model_name: str, model_path: Path) -> None:
        with self._lock:
            if self._llm is not None and self._model_name == model_name:
                return
            try:
                from vllm import LLM, SamplingParams
            except ImportError as exc:
                raise RuntimeError(
                    "vLLM is not available. "
                    "Install with: pip install vllm (requires Linux + NVIDIA GPU)"
                ) from exc

            model_dir = str(model_path)
            logger.info("loading vllm model name=%s path=%s", model_name, model_dir)
            self._llm = LLM(model=model_dir)
            self._sampling_params_cls = SamplingParams
            self._model_name = model_name

            # 缓存 tokenizer（用于 chat_template 格式化）
            try:
                self._tokenizer = self._llm.get_tokenizer()
            except Exception as e:
                logger.warning("failed to get vllm tokenizer: %s", e)
                self._tokenizer = None

            # 检测 structured_outputs 可用性
            try:
                from vllm import StructuredOutputsParams  # noqa: F401
                self._structured_outputs_available = True
                logger.info("vLLM StructuredOutputsParams available, guided decoding enabled")
            except ImportError:
                self._structured_outputs_available = False
                logger.info("vLLM StructuredOutputsParams not available, using post-parse only")

            self._model_type = detect_model_type(model_name)
            self._default_stop = _get_default_stop(model_name)

            # 推断 reasoning parser
            probe = detect_reasoning_parser(model_name)
            self._reasoning_parser_name = type(probe).__name__ if probe else None

            logger.info(
                "vllm model loaded name=%s model_type=%s default_stop=%s reasoning_parser=%s",
                model_name, self._model_type or "auto",
                self._default_stop or "none",
                self._reasoning_parser_name or "none",
            )

    # ------------------------------------------------------------------
    # prompt 格式化
    # ------------------------------------------------------------------

    def _format_prompt(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> str:
        """使用 tokenizer chat_template 格式化（替代简单字符串拼接）。

        若 tokenizer 不可用或 chat_template 不支持，回退到简单拼接。
        """
        if self._tokenizer is not None and hasattr(self._tokenizer, "apply_chat_template"):
            try:
                dict_messages = [{"role": m.role, "content": m.content or ""} for m in messages]
                kwargs: dict[str, Any] = {"tokenize": False, "add_generation_prompt": True}
                if tools:
                    kwargs["tools"] = tools
                return self._tokenizer.apply_chat_template(dict_messages, **kwargs)
            except Exception as e:
                logger.debug("chat_template failed, fallback to simple concat: %s", e)

        # 回退：简单拼接
        parts = []
        for m in messages:
            prefix = {"system": "System", "user": "User", "assistant": "Assistant", "tool": "Tool"}.get(
                m.role, m.role.capitalize()
            )
            parts.append(f"{prefix}: {m.content or ''}")
        parts.append("Assistant:")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # sampling params
    # ------------------------------------------------------------------

    def _build_sampling_params(self, request: ChatCompletionRequest) -> Any:
        """构建 vLLM SamplingParams，FC 场景注入 structured_outputs 约束。"""
        ec = self._engine_config
        temperature = request.temperature
        max_tokens = request.max_tokens

        kwargs: dict[str, Any] = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": request.top_p,
            "n": request.n,
        }
        # 合并请求 stop + 模型默认 stop 序列（去重）
        all_stop = list(dict.fromkeys(
            (request.stop or []) + self._default_stop
        ))
        if all_stop:
            kwargs["stop"] = all_stop
        if request.presence_penalty:
            kwargs["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty:
            kwargs["frequency_penalty"] = request.frequency_penalty
        if request.seed is not None:
            kwargs["seed"] = request.seed
        if request.logprobs:
            kwargs["logprobs"] = request.top_logprobs or 1

        # Function Call 场景：注入 structured_outputs JSON Schema 约束
        dict_tools = ToolCallParser.tools_to_dict_list(request.tools) if request.tools else None
        if dict_tools and request.tool_choice != "none":
            # 降温 + 限制 max_tokens
            kwargs["temperature"] = min(temperature, ec.tool_call_temperature)
            kwargs["max_tokens"] = min(max_tokens, ec.tool_call_max_tokens)

            if self._structured_outputs_available:
                try:
                    from vllm import StructuredOutputsParams
                    tool_schema = ToolCallParser.build_tool_call_json_schema(dict_tools)
                    kwargs["structured_outputs"] = StructuredOutputsParams(json=tool_schema)
                    logger.info("vLLM structured_outputs enabled with JSON schema constraint")
                except Exception as e:
                    logger.warning("failed to inject structured_outputs: %s", e)

        return self._sampling_params_cls(**kwargs)

    # ------------------------------------------------------------------
    # 非流式生成
    # ------------------------------------------------------------------

    def chat_complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        """非流式 Chat Completions，FC 通过 structured_outputs + ToolCallParser 校验。"""
        dict_tools = ToolCallParser.tools_to_dict_list(request.tools) if request.tools else None

        with self._lock:
            if self._llm is None or self._sampling_params_cls is None:
                raise RuntimeError("model engine is not ready")

            prompt = self._format_prompt(request.messages, dict_tools)
            sampling_params = self._build_sampling_params(request)
            outputs = self._llm.generate([prompt], sampling_params)

        req_output = outputs[0]
        prompt_tokens = len(req_output.prompt_token_ids or [])
        choices = []
        total_completion = 0
        tc_metrics: ToolCallMetrics | None = None

        for i, out in enumerate(req_output.outputs):
            completion_tokens = len(out.token_ids or [])
            total_completion += completion_tokens

            # 统一 ToolCallParser 解析
            tool_calls = None
            if dict_tools:
                parse_result = self._tc_parser.parse(
                    out.text, dict_tools, request.tool_choice,
                    model_type=self._model_type,
                )
                tool_calls = parse_result.calls
                tc_metrics = parse_result.metrics

            content = out.text if not tool_calls else None
            choices.append(
                ChatChoice(
                    index=i,
                    message=ChatMessage(
                        role="assistant",
                        content=content,
                        tool_calls=tool_calls,
                    ),
                    finish_reason="tool_calls" if tool_calls else (out.finish_reason or "stop"),
                )
            )

        usage = UsageStats(
            prompt_tokens=prompt_tokens,
            completion_tokens=total_completion,
            total_tokens=prompt_tokens + total_completion,
        )
        return ChatCompletionResult(choices=choices, usage=usage, tool_call_metrics=tc_metrics)

    # ------------------------------------------------------------------
    # 流式生成
    # ------------------------------------------------------------------

    def stream_chat_complete(
        self, request: ChatCompletionRequest,
    ) -> Generator[ChatCompletionChunkResult, None, None]:
        """流式 Chat Completions — vLLM generate 一次性返回后模拟逐 token yield。"""
        dict_tools = ToolCallParser.tools_to_dict_list(request.tools) if request.tools else None

        with self._lock:
            if self._llm is None or self._sampling_params_cls is None:
                raise RuntimeError("model engine is not ready")

            prompt = self._format_prompt(request.messages, dict_tools)
            sampling_params = self._build_sampling_params(request)
            outputs = self._llm.generate([prompt], sampling_params)

        req_output = outputs[0]
        prompt_tokens = len(req_output.prompt_token_ids or [])

        for out in req_output.outputs:
            text = out.text
            completion_tokens = len(out.token_ids or [])

            # 逐字符模拟流式输出
            for char in text:
                yield ChatCompletionChunkResult(
                    choices=[
                        StreamChoice(
                            index=out.index,
                            delta=StreamDelta(content=char),
                        )
                    ]
                )

            # 流结束后解析 tool_calls
            tool_calls = None
            if dict_tools:
                parse_result = self._tc_parser.parse(
                    text, dict_tools, request.tool_choice,
                    model_type=self._model_type,
                )
                tool_calls = parse_result.calls

            finish_reason = "tool_calls" if tool_calls else (out.finish_reason or "stop")
            final_delta = StreamDelta()
            if tool_calls:
                final_delta.tool_calls = tool_calls

            yield ChatCompletionChunkResult(
                choices=[
                    StreamChoice(
                        index=out.index,
                        delta=final_delta,
                        finish_reason=finish_reason,
                    )
                ],
                usage=UsageStats(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
            )
