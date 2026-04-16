"""MLX inference engine — for Apple Silicon (M-series) Macs.

Auto-detects LLM vs VLM model types:
  - LLM: mlx_lm (pip install mlx-lm)
  - VLM: mlx_vlm (pip install mlx-vlm)

Features:
  - Non-streaming / streaming
  - Tools (via chat_template inference)
  - reasoning_content (auto-detect DeepSeek R1 / Qwen3 etc.)
  - n (degraded to loop)

Performance (controlled by EngineConfig):
  - Tokenizer CPU thread pool offloading
  - KV Cache paged management (RotatingKVCache)
  - Adaptive prefill: dynamic step_size based on prompt length + available memory
  - Short prompt fast-path: skip chunked prefill for small prompts
  - Inference serial protection: MLX Metal thread-safety constraint
  - Full observability: prefill_ms / decode_ms / lock_wait_ms / tok_s metrics
"""

from __future__ import annotations

import gc
import importlib
import json
import logging
import re
import threading
import time as _time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Generator, Optional

from .base import (
    ChatChoice,
    ChatCompletionChunkResult,
    ChatCompletionRequest,
    ChatCompletionResult,
    ChatMessage,
    CompletionTokensDetails,
    LLMEngine,
    StreamChoice,
    StreamDelta,
    ToolCallResult,
    UsageStats,
)
from .reasoning import ReasoningParser, detect_reasoning_parser
from .outlines_mlx_provider import OutlinesMLXProvider
from .mlx_import import ensure_mlx_available
from .tool_call_parser import (
    ToolCallMetrics, ToolCallParseResult, ToolCallParser, detect_model_type,
)

logger = logging.getLogger(__name__)


# ─────────── Inference Metrics ───────────

class InferMetrics:
    """Per-request inference timing metrics for observability.

    Captures fine-grained timing: lock wait, prefill, decode phases,
    and derived throughput (tok/s). Designed to be cheap (no allocations
    in hot path) and serializable to log / stats.
    """
    __slots__ = (
        "lock_wait_ms", "prefill_ms", "decode_ms", "total_ms",
        "prompt_tokens", "completion_tokens",
        "prefill_step_size", "prompt_length",
    )

    def __init__(self) -> None:
        self.lock_wait_ms: int = 0
        self.prefill_ms: int = 0
        self.decode_ms: int = 0
        self.total_ms: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.prefill_step_size: int = 0
        self.prompt_length: int = 0

    @property
    def prefill_tok_s(self) -> float:
        """Prefill throughput (tok/s). Returns 0 if prefill_ms is 0."""
        return (self.prompt_tokens * 1000.0 / self.prefill_ms) if self.prefill_ms > 0 else 0.0

    @property
    def decode_tok_s(self) -> float:
        """Decode throughput (tok/s). Returns 0 if decode_ms is 0."""
        return (self.completion_tokens * 1000.0 / self.decode_ms) if self.decode_ms > 0 else 0.0

    def log_summary(self, request_id: str = "") -> None:
        """Emit a single structured log line with all timing metrics."""
        logger.info(
            "infer_metrics request_id=%s prompt_tokens=%d completion_tokens=%d "
            "lock_wait_ms=%d prefill_ms=%d decode_ms=%d total_ms=%d "
            "prefill_tok_s=%.1f decode_tok_s=%.1f prefill_step_size=%d",
            request_id, self.prompt_tokens, self.completion_tokens,
            self.lock_wait_ms, self.prefill_ms, self.decode_ms, self.total_ms,
            self.prefill_tok_s, self.decode_tok_s, self.prefill_step_size,
        )


# ─────────── Adaptive Prefill Strategy ───────────

# Short prompt threshold: below this, skip chunked prefill entirely
# (let MLX process in a single eval — lower overhead, no tqdm progress bar)
_SHORT_PROMPT_THRESHOLD = 2048

# Prefill step tiers: (min_prompt_len, step_size)
# Larger steps → fewer eval rounds → faster; but higher peak memory.
# Ordered from longest prompts to shortest for quick lookup.
_PREFILL_STEP_TIERS = [
    (16384, 2048),   # very long context: large steps for throughput
    (8192,  1536),   # long context
    (4096,  1024),   # medium context
    (2048,   768),   # moderate context
]


def _compute_adaptive_prefill_step(
    prompt_tokens: int,
    base_step: int,
    available_mem_gb: float,
) -> int:
    """Compute optimal prefill_step_size based on prompt length and available memory.

    Strategy:
      1. Short prompts (< _SHORT_PROMPT_THRESHOLD) → return 0 (skip chunked prefill).
      2. Select tier step from _PREFILL_STEP_TIERS by prompt length.
      3. Scale down if available memory is low (< 8 GB → halve the step).
      4. Clamp to [256, base_step * 2] to stay within safe bounds.

    Args:
        prompt_tokens: Number of tokens in the prompt.
        base_step: The static prefill_step_size from EngineConfig.
        available_mem_gb: Current available system memory in GB.

    Returns:
        Optimal prefill_step_size, or 0 to skip chunked prefill.
    """
    # Short prompts: single-shot eval, no chunking overhead
    if prompt_tokens < _SHORT_PROMPT_THRESHOLD:
        return 0

    # Find the matching tier
    step = base_step
    for min_len, tier_step in _PREFILL_STEP_TIERS:
        if prompt_tokens >= min_len:
            step = tier_step
            break

    # Memory pressure: scale down under low memory to prevent OOM
    if available_mem_gb < 8.0:
        step = max(256, step // 2)
    elif available_mem_gb < 16.0:
        step = max(256, int(step * 0.75))

    # Clamp to safe bounds
    step = max(256, min(step, base_step * 2))
    return step

# ─────────── 模型默认 stop 序列 ───────────
# Different models define their own EOS/stop tokens in chat_template, but
# mlx_lm stream_generate does not handle them automatically — we must
# truncate in post-processing. This mapping injects stop post-processing.
#
# Gemma 3 (gemma3/gemma3n): uses <start_of_turn> / <end_of_turn>
# Gemma 4: uses <|turn> / <turn|> (new control tokens since gemma4)
_MODEL_STOP_SEQUENCES: dict[str, list[str]] = {
    "glm": [
        "<|user|>", "<|observation|>", "<|endoftext|>", "<|assistant|>",
    ],
    "qwen": [
        "<|im_end|>", "<|im_start|>", "<|endoftext|>",
    ],
    "deepseek": [
        "<|end▁of▁sentence|>", "<｜end▁of▁sentence｜>",
    ],
    "kimi": [
        "<|im_end|>", "<|endoftext|>",
    ],
    "llama": [
        "<|eot_id|>", "<|end_of_text|>",
    ],
    "mistral": [
        "</s>",
    ],
    "gemma3": [
        "<end_of_turn>", "<start_of_turn>",
    ],
    "gemma4": [
        "<turn|>", "<|turn>", "<|tool_response>", "<channel|>",
    ],
}


def _get_model_stop_sequences(model_name: str) -> list[str]:
    """Return default stop sequences for the given model name.

    Gemma family requires special handling: gemma4 must be checked before
    gemma3 because "gemma3" would otherwise match "gemma3n" variants.
    The lookup order ensures more specific keys match first.
    """
    name_lower = model_name.lower()
    # Gemma family: check gemma4 first, then gemma3, then fallback to gemma3
    # for any other gemma variant (e.g. future gemma5 still uses turn tokens)
    if "gemma" in name_lower:
        if "gemma4" in name_lower or "gemma-4" in name_lower:
            return _MODEL_STOP_SEQUENCES["gemma4"]
        # gemma3, gemma3n, gemma-3, or any older gemma variant
        return _MODEL_STOP_SEQUENCES["gemma3"]
    for key, stops in _MODEL_STOP_SEQUENCES.items():
        if key in name_lower:
            return stops
    return []


# ─────────── Special token cleanup ───────────
# Filter residual special tokens from model output.
# IMPORTANT: Gemma4 tool_call tokens (<|tool_call>, <tool_call|>, <|"|>) are
# deliberately EXCLUDED here — they must survive until after tool call parsing.
# They are cleaned in a separate post-parse phase via _GEMMA4_TOOL_TOKENS_RE.
_SPECIAL_TOKENS_RE = re.compile(
    r"<\|im_end\|>|<\|im_start\|>|<\|endoftext\|>|"
    r"<\|end\|>|<\|eot_id\|>|<\|start_header_id\|>|<\|end_header_id\|>|"
    r"<\|observation\|>|<\|user\|>|<\|assistant\|>|"
    r"<\|end_of_text\|>|<\|end▁of▁sentence\|>|<｜end▁of▁sentence｜>|"
    # Gemma 3 control tokens
    r"<end_of_turn>|<start_of_turn>|"
    # Gemma 4 turn control tokens (NOT tool_call tokens)
    r"<\|turn>|<turn\|>|"
    # Gemma 4 channel tokens (thinking/reasoning delimiters)
    r"<\|channel>thought|<\|channel>|<channel\|>|"
    r"</s>|<s>|<pad>|\[PAD\]|\[SEP\]|\[CLS\]"
)

# Kimi tool_call delimiter tokens (cleaned after tool_call parsing)
_KIMI_TOOL_TOKENS_RE = re.compile(
    r"<\|tool_call_begin\|>|<\|tool_call_end\|>|"
    r"<\|tool_calls_section_begin\|>|<\|tool_calls_section_end\|>|"
    r"<\|tool_call_argument_begin\|>"
)

# Gemma4 tool_call tokens — cleaned ONLY after tool call parsing is complete.
# Includes: <|tool_call>, <tool_call|>, <|tool_response>, <tool_response|>,
# <|tool>, <tool|>, <|"|> (parameter quoting token)
_GEMMA4_TOOL_TOKENS_RE = re.compile(
    r'<\|tool_call>|<tool_call\|>|<\|tool_response>|<tool_response\|>|'
    r'<\|tool>|<tool\|>|<\|"\|>'
)


# ─────────── Gemma4 Chat Template ───────────
# Official Gemma4 prompt format per:
#   https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4
#   https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4
#
# Injected at runtime when the model's tokenizer lacks a built-in chat_template.
# Supports: system, user, model/assistant, tools, tool_calls, tool_responses,
# and optional thinking mode via enable_thinking parameter.

_GEMMA4_CHAT_TEMPLATE = """\
{%- set ns = namespace(tool_decls='', think_mode=false) -%}

{#- Determine if thinking mode is enabled -#}
{%- if enable_thinking is defined and enable_thinking -%}
  {%- set ns.think_mode = true -%}
{%- endif -%}

{#- Build tool declarations string -#}
{%- if tools is defined and tools -%}
  {%- for tool in tools -%}
    {%- if tool.function is defined -%}
      {%- set func = tool.function -%}
      {%- set decl = 'declaration:' + func.name + '{' -%}
      {%- if func.description is defined and func.description -%}
        {%- set decl = decl + 'description:<|"|>' + func.description + '<|"|>,' -%}
      {%- endif -%}
      {%- if func.parameters is defined and func.parameters -%}
        {%- set decl = decl + 'parameters:<|"|>' + func.parameters | tojson + '<|"|>' -%}
      {%- endif -%}
      {%- set decl = decl + '}' -%}
      {%- set ns.tool_decls = ns.tool_decls + '<|tool>' + decl + '<tool|>' -%}
    {%- endif -%}
  {%- endfor -%}
{%- endif -%}

{#- Render messages -#}
{%- for message in messages -%}
  {%- set role = message.role -%}
  {%- if role == 'assistant' -%}
    {%- set role = 'model' -%}
  {%- endif -%}

  {%- if role == 'system' -%}
<|turn>system
{% if ns.think_mode %}<|think|>{% endif %}{{ message.content }}{{ ns.tool_decls }}<turn|>
  {%- elif role == 'user' -%}
    {#- If no system message was given yet and we have tool decls, inject them -#}
    {%- if loop.first and ns.tool_decls -%}
<|turn>system
{% if ns.think_mode %}<|think|>{% endif %}{{ ns.tool_decls }}<turn|>
    {%- endif -%}
<|turn>user
{{ message.content }}<turn|>
  {%- elif role == 'model' -%}
<|turn>model
{{ message.content }}
    {#- Render tool_calls if present -#}
    {%- if message.tool_calls is defined and message.tool_calls -%}
      {%- for tc in message.tool_calls -%}
        {%- set func = tc.function if tc.function is defined else tc -%}
        {%- set args = func.arguments -%}
<|tool_call>call:{{ func.name }}{
        {%- for key, value in args.items() -%}
{{ key }}:<|"|>{{ value }}<|"|>{% if not loop.last %},{% endif %}
        {%- endfor -%}
}<tool_call|>
      {%- endfor -%}
    {%- endif -%}
    {#- Render tool_responses if present -#}
    {%- if message.tool_responses is defined and message.tool_responses -%}
<|turn>model
      {%- for tr in message.tool_responses -%}
<|tool_response>response:{{ tr.name }}{{ tr.response | tojson }}<tool_response|>
      {%- endfor -%}
    {%- endif -%}
<turn|>
  {%- elif role == 'tool' -%}
    {#- OpenAI-style role=tool; skip — handled via tool_responses on assistant msg -#}
  {%- endif -%}
{%- endfor -%}

{#- Generation prompt -#}
{%- if add_generation_prompt -%}
<|turn>model
{%- endif -%}
"""


def _clean_special_tokens(
    text: str,
    include_tool_tokens: bool = False,
    include_gemma4_tokens: bool = False,
) -> str:
    """Remove residual special tokens from model output.

    Args:
        text: Raw model output text.
        include_tool_tokens: Also clean Kimi tool_call delimiter tokens.
        include_gemma4_tokens: Also clean Gemma4 tool_call/response tokens.
            Must only be True AFTER tool call parsing is complete.
    """
    result = _SPECIAL_TOKENS_RE.sub("", text)
    if include_tool_tokens:
        result = _KIMI_TOOL_TOKENS_RE.sub("", result)
    if include_gemma4_tokens:
        result = _GEMMA4_TOOL_TOKENS_RE.sub("", result)
    return result


def _truncate_at_stop(text: str, stop_sequences: list[str]) -> str:
    """在首个 stop 序列处硬截断文本，防止模型续写下一轮对话。

    这是解决 GLM/Qwen 等模型生成 <|user|> 后垃圾续写的关键防线。
    """
    if not stop_sequences:
        return text
    earliest_pos = len(text)
    for stop in stop_sequences:
        pos = text.find(stop)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
    if earliest_pos < len(text):
        logger.debug("truncated output at stop sequence, pos=%d", earliest_pos)
        return text[:earliest_pos]
    return text


def _is_vlm(model_dir: str) -> bool:
    """检测模型目录是否为 VLM（包含视觉编码器配置）。"""
    config_path = Path(model_dir) / "config.json"
    if not config_path.exists():
        return False
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        vlm_keys = {"vision_config", "visual", "vision_tower", "mm_vision_tower"}
        return bool(vlm_keys & cfg.keys())
    except Exception:
        return False


def _messages_to_dict_list(messages: list[ChatMessage], model_type: str = "") -> list[dict]:
    """Convert ChatMessage list to dict format for chat template.

    Model-specific adaptations:
      - GLM: maps role="tool" to "observation".
      - Gemma 3: system messages merged into first user message.
      - Gemma 4: role="tool" → tool_responses on preceding assistant message.
    """
    result = []

    is_gemma3 = model_type in ("gemma3", "gemma3n")
    is_gemma4 = model_type == "gemma4"
    system_content_for_merge = ""
    if is_gemma3:
        for m in messages:
            if m.role == "system" and m.content:
                system_content_for_merge += m.content + "\n\n"

    # Debug: log input message structure
    logger.debug(
        "messages_to_dict: model_type=%s is_gemma4=%s msg_count=%d roles=[%s]",
        model_type, is_gemma4, len(messages),
        ", ".join(f"{m.role}(tc={bool(m.tool_calls)},tcid={bool(m.tool_call_id)},name={m.name})"
                  for m in messages),
    )

    first_user_seen = False
    gemma4_tool_merged = 0
    for idx, m in enumerate(messages):
        role = m.role

        if is_gemma3 and role == "system":
            continue

        if model_type == "glm" and role == "tool":
            role = "observation"

        # Gemma 4: merge role=tool into preceding assistant's tool_responses
        if is_gemma4 and m.role == "tool":
            if result:
                prev = result[-1]
                if prev.get("role") == "assistant":
                    if "tool_responses" not in prev:
                        prev["tool_responses"] = []
                    response_data = m.content or ""
                    try:
                        response_data = json.loads(response_data)
                    except (json.JSONDecodeError, TypeError):
                        pass

                    # Resolve function name: prefer m.name, fallback to matching
                    # tool_call_id in the preceding assistant's tool_calls.
                    # Upstream clients often omit name on role=tool messages.
                    func_name = m.name or ""
                    if not func_name and m.tool_call_id and prev.get("tool_calls"):
                        for tc in prev["tool_calls"]:
                            if tc.get("id") == m.tool_call_id:
                                func_name = tc.get("function", {}).get("name", "")
                                break
                    # Last resort: if only one tool_call, use its name
                    if not func_name and prev.get("tool_calls") and len(prev["tool_calls"]) == 1:
                        func_name = prev["tool_calls"][0].get("function", {}).get("name", "")

                    if not func_name:
                        logger.warning(
                            "gemma4: tool_response at idx=%d has no function name "
                            "(name=%s, tool_call_id=%s), model may not correlate response",
                            idx, m.name, m.tool_call_id,
                        )

                    prev["tool_responses"].append({
                        "name": func_name,
                        "response": response_data,
                    })
                    gemma4_tool_merged += 1
                    logger.debug(
                        "gemma4: merged tool_response[%d] name=%s (resolved from %s) "
                        "into assistant (content_len=%d)",
                        gemma4_tool_merged, func_name,
                        "msg.name" if m.name else "tool_call_id" if func_name else "none",
                        len(m.content or ""),
                    )
                    continue
                else:
                    logger.warning(
                        "gemma4: tool msg at idx=%d but prev role=%s (expected assistant), "
                        "tool_call_id=%s name=%s",
                        idx, prev.get("role"), m.tool_call_id, m.name,
                    )
            logger.warning(
                "gemma4: orphan tool msg at idx=%d, no preceding assistant, "
                "tool_call_id=%s name=%s content=%s",
                idx, m.tool_call_id, m.name, (m.content or "")[:100],
            )
            continue

        msg: dict[str, Any] = {"role": role, "content": m.content or ""}

        if is_gemma3 and role == "user" and not first_user_seen and system_content_for_merge:
            msg["content"] = system_content_for_merge + (m.content or "")
            first_user_seen = True
        elif role == "user":
            first_user_seen = True

        # Prepend reasoning_content from historical assistant messages
        if m.role == "assistant" and m.reasoning_content:
            if is_gemma4:
                msg["content"] = f"<|channel>thought\n{m.reasoning_content}\n<channel|>{m.content or ''}"
            else:
                msg["content"] = f"<think>{m.reasoning_content}</think>{m.content or ''}"
        if m.tool_calls:
            tc_list = []
            for tc in m.tool_calls:
                args = tc.function_arguments
                if is_gemma4 and isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        pass
                tc_list.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function_name, "arguments": args},
                })
            msg["tool_calls"] = tc_list
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        if m.name:
            msg["name"] = m.name
        result.append(msg)

    # Debug: log output structure
    if is_gemma4:
        for i, d in enumerate(result):
            has_tc = "tool_calls" in d
            has_tr = "tool_responses" in d
            tr_count = len(d.get("tool_responses", []))
            tc_count = len(d.get("tool_calls", []))
            if has_tc or has_tr:
                logger.debug(
                    "gemma4 dict_msg[%d] role=%s tool_calls=%d tool_responses=%d",
                    i, d.get("role"), tc_count, tr_count,
                )
        if gemma4_tool_merged == 0 and any(m.role == "tool" for m in messages):
            logger.warning(
                "gemma4: %d tool messages in input but 0 merged — "
                "tool_responses may be missing from prompt!",
                sum(1 for m in messages if m.role == "tool"),
            )

    return result


def _tools_to_dict_list(tools: list | None) -> list[dict] | None:
    """将 ToolDef 列表转为 dict 格式。"""
    if not tools:
        return None
    return [
        {
            "type": t.type,
            "function": {
                "name": t.function.name,
                "description": t.function.description or "",
                "parameters": t.function.parameters,
            },
        }
        for t in tools
        if t.function
    ]


class VLLMMLXEngine(LLMEngine):
    """MLX 推理引擎，自动区分 LLM / VLM 并使用对应后端。

    - LLM: mlx_lm.load / generate / stream_generate
    - VLM: mlx_vlm.load / generate / stream_generate
    - 推理模型自动检测 reasoning parser（DeepSeek R1 / Qwen3 等）

    MLX Metal 线程安全约束：
      Metal command buffer 不支持多线程并发提交，_infer_lock 在整个推理
      stream 期间持有，确保 GPU 同一时刻只服务一个推理请求。
      将 tokenize/detokenize 移出锁范围，减少锁内 wall time。
    """

    def __init__(self, engine_config: "EngineConfig | None" = None) -> None:
        from config import EngineConfig

        self._engine_config = engine_config or EngineConfig()
        self._lock = threading.Lock()
        # Metal GPU 不支持多线程并发编码 command buffer，
        # 必须用互斥锁串行化所有推理请求
        self._infer_lock = threading.Lock()
        self._model: Any | None = None
        self._processor: Any | None = None  # LLM 模式下为 tokenizer
        self._config: Any | None = None
        self._model_name: str = ""
        self._is_vlm: bool = False
        # tool parser（按 chat_template 自动推断）
        self._tool_parser_type: Optional[str] = None
        self._tool_module: Any | None = None
        # reasoning parser 类型名称（按模型名称自动推断），实例在每次请求时独立创建
        self._reasoning_parser_name: str | None = None
        # Tool call format type ("glm47" / "kimi" / "" etc.) for parser selection
        self._model_type: str = ""
        # Chat format variant for message pre-processing (e.g. "gemma3", "gemma4", "glm")
        self._chat_format: str = ""
        # Model default stop sequences (post-processing hard truncation + token detection)
        self._stop_sequences: list[str] = []
        # 统一 FC 解析器 + outlines-mlx 约束解码
        self._tc_parser = ToolCallParser()
        self._outlines_provider = OutlinesMLXProvider()

        # Tokenizer CPU 线程池：将编码/解码操作卸载到 CPU，不占 GPU
        ec = self._engine_config
        if ec.tokenizer_prefer_cpu and ec.tokenizer_workers > 0:
            self._tokenizer_pool: ThreadPoolExecutor | None = ThreadPoolExecutor(
                max_workers=ec.tokenizer_workers,
                thread_name_prefix="tokenizer-cpu",
            )
            logger.info("tokenizer CPU pool created: workers=%d", ec.tokenizer_workers)
        else:
            self._tokenizer_pool = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def ready(self) -> bool:
        return self._model is not None

    def unload(self) -> None:
        """卸载模型并释放 Metal GPU 资源和 Tokenizer 线程池。"""
        with self._lock:
            if self._model is None:
                return
            model_name = self._model_name
            logger.info("unloading model name=%s", model_name)

            # 释放模型和处理器引用
            self._model = None
            self._processor = None
            self._config = None
            self._model_name = ""
            self._tool_parser_type = None
            self._tool_module = None
            self._reasoning_parser_name = None
            self._model_type = ""
            self._chat_format = ""
            self._stop_sequences = []

            # 关闭 Tokenizer CPU 线程池
            if self._tokenizer_pool is not None:
                self._tokenizer_pool.shutdown(wait=False)
                self._tokenizer_pool = None

            # 强制清理 Metal GPU 缓存和 Python 对象（unload 时允许 GC）
            try:
                import mlx.core as mx
                mx.clear_cache()
            except Exception:
                pass
            gc.collect()

            logger.info("model unloaded name=%s, GPU cache cleared", model_name)

    def load(self, model_name: str, model_path: Path) -> None:
        """加载模型，自动检测 LLM/VLM 类型 + 推理解析器。"""
        # 首次加载前确保 mlx 通过隔离导入机制安全加载（防止 nanobind 重复注册）
        ensure_mlx_available()

        with self._lock:
            if self._model is not None and self._model_name == model_name:
                return

            model_dir = str(model_path)
            self._is_vlm = _is_vlm(model_dir)
            backend = "mlx_vlm" if self._is_vlm else "mlx_lm"
            logger.info(
                "loading model name=%s path=%s backend=%s",
                model_name, model_dir, backend,
            )

            if self._is_vlm:
                try:
                    from mlx_vlm import load as vlm_load
                except ImportError as exc:
                    raise RuntimeError("pip install mlx-vlm") from exc
                try:
                    self._model, self._processor = vlm_load(model_dir)
                except (ValueError, ModuleNotFoundError) as exc:
                    # mlx_vlm may not support this model type yet (e.g. gemma4).
                    # Fallback to mlx_lm for text-only inference using the
                    # text decoder portion of the multimodal architecture.
                    logger.warning(
                        "mlx_vlm does not support this model, "
                        "falling back to mlx_lm for text-only inference: %s", exc,
                    )
                    self._is_vlm = False
                    backend = "mlx_lm"
                    from mlx_lm import load as lm_load
                    self._model, self._processor = lm_load(model_dir)
            else:
                try:
                    from mlx_lm import load as lm_load
                except ImportError as exc:
                    raise RuntimeError("pip install mlx-lm") from exc
                self._model, self._processor = lm_load(model_dir)

            self._config = self._model.config if hasattr(self._model, "config") else None
            self._model_name = model_name

            # Gemma4 models may ship without a built-in chat_template.
            # Inject the official template so apply_chat_template works correctly,
            # especially for multi-turn tool call conversations.
            self._ensure_gemma4_chat_template(model_name)

            # Register model-specific stop tokens as EOS tokens in tokenizer.
            # mlx_lm.stream_generate 只通过 tokenizer.eos_token_ids 检测停止，
            # 不接受 stop 参数。必须在 token 层面注册，才能让生成在遇到这些 token 时立即停止。
            self._register_extra_eos_tokens(model_name)

            self._init_tool_parser()
            # 根据模型名称推断 reasoning parser 类型（每次请求独立创建实例避免并发状态竞争）
            probe = detect_reasoning_parser(model_name)
            if probe is not None:
                self._reasoning_parser_name = type(probe).__name__
            else:
                self._reasoning_parser_name = None

            # Detect tool call format type for parser selection
            self._model_type = detect_model_type(model_name)

            # Detect chat format variant for message pre-processing.
            # Prefer config.model_type (set by HF model configs) for accuracy.
            self._chat_format = self._detect_chat_format(model_name)

            # Set model default stop sequences (post-processing hard truncation)
            self._stop_sequences = _get_model_stop_sequences(model_name)

            # outlines-mlx 模型加载（仅配置需要时）
            strategy = self._engine_config.tool_call_strategy
            if strategy in ("outlines_only", "parser_fallback_outlines") and self._outlines_provider.detected:
                self._outlines_provider.load_model(model_dir)

            logger.info(
                "model loaded name=%s backend=%s reasoning_parser=%s "
                "model_type=%s chat_format=%s stop_sequences=%s tool_call_strategy=%s",
                model_name, backend, self._reasoning_parser_name or "none",
                self._model_type or "auto", self._chat_format or "default",
                self._stop_sequences or "none", strategy,
            )

    # ------------------------------------------------------------------
    # tokenizer 访问
    # ------------------------------------------------------------------

    def _get_tokenizer(self) -> Any:
        """统一获取 tokenizer。"""
        if self._is_vlm and hasattr(self._processor, "tokenizer"):
            return self._processor.tokenizer
        return self._processor

    def _tokenize_on_cpu(self, text: str) -> list[int]:
        """在 CPU 线程池中执行 tokenizer.encode，不占 GPU。

        如果未启用 tokenizer CPU 线程池，则直接在当前线程执行。
        """
        tokenizer = self._get_tokenizer()
        if self._tokenizer_pool is not None:
            future = self._tokenizer_pool.submit(tokenizer.encode, text)
            return future.result()
        return tokenizer.encode(text)

    def _detokenize_on_cpu(self, token_ids: list[int]) -> str:
        """在 CPU 线程池中执行 tokenizer.decode，不占 GPU。"""
        tokenizer = self._get_tokenizer()
        if self._tokenizer_pool is not None:
            future = self._tokenizer_pool.submit(tokenizer.decode, token_ids)
            return future.result()
        return tokenizer.decode(token_ids)

    def _count_tokens_on_cpu(self, text: str) -> int:
        """在 CPU 线程池中对文本做精确 token 计数。"""
        if not text:
            return 0
        token_ids = self._tokenize_on_cpu(text)
        return len(token_ids)

    # ------------------------------------------------------------------
    # Gemma4 chat template injection
    # ------------------------------------------------------------------

    def _ensure_gemma4_chat_template(self, model_name: str) -> None:
        """Inject Gemma4 chat template if the tokenizer doesn't have one.

        Many Gemma4 model variants (e.g. E4B quantized) ship without a
        chat_template in tokenizer_config.json. Without a proper template,
        apply_chat_template fails or produces malformed prompts — causing
        the model to ignore tool results and repeat the same tool call.

        The template follows the official Gemma4 prompt formatting spec:
        https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4
        """
        name_lower = model_name.lower()
        if not ("gemma4" in name_lower or "gemma-4" in name_lower):
            return

        tokenizer = self._get_tokenizer()
        # Check both wrapper and inner tokenizer
        wrapper_ct = getattr(tokenizer, "chat_template", None)
        inner_ct = None
        if hasattr(tokenizer, "_tokenizer"):
            inner_ct = getattr(tokenizer._tokenizer, "chat_template", None)
        has_template = wrapper_ct is not None or inner_ct is not None

        logger.info(
            "gemma4 chat_template check: wrapper_has=%s inner_has=%s wrapper_type=%s",
            wrapper_ct is not None, inner_ct is not None, type(tokenizer).__name__,
        )

        if has_template:
            logger.info("gemma4 model already has chat_template, skipping injection")
            return

        logger.info(
            "gemma4 model has NO chat_template, injecting official template "
            "(len=%d, is_vlm=%s, tokenizer_type=%s)",
            len(_GEMMA4_CHAT_TEMPLATE), self._is_vlm, type(tokenizer).__name__,
        )

        # Set chat_template on the tokenizer that apply_chat_template uses.
        # For VLM (GemmaTokenizer): set directly on the tokenizer object.
        # For LLM (TokenizerWrapper): set on the inner HF tokenizer, since
        # the wrapper delegates to _tokenizer.apply_chat_template().
        tokenizer.chat_template = _GEMMA4_CHAT_TEMPLATE
        # Also set on the inner tokenizer if it exists (for LLM TokenizerWrapper)
        inner = getattr(tokenizer, "_tokenizer", None)
        if inner is not None and hasattr(inner, "chat_template"):
            inner.chat_template = _GEMMA4_CHAT_TEMPLATE

        # Flag the wrapper as having a template
        if hasattr(tokenizer, "has_chat_template"):
            tokenizer.has_chat_template = True

        # Verify injection succeeded
        verify = getattr(tokenizer, "chat_template", None)
        logger.info("gemma4 chat_template injection verified: %s", verify is not None)

    # ------------------------------------------------------------------
    # tool parser
    # ------------------------------------------------------------------

    def _register_extra_eos_tokens(self, model_name: str) -> None:
        """Register model-specific stop tokens as extra EOS tokens in tokenizer.

        mlx_lm.stream_generate only stops via tokenizer.eos_token_ids,
        it does not accept a custom stop parameter. We must register each
        model's stop tokens (e.g. GLM's <|user|>, Qwen's <|im_end|>,
        Gemma3's <end_of_turn>, Gemma4's <turn|>) as EOS tokens so the
        generator stops at the token level immediately.

        Uses TokenizerWrapper.add_eos_token() which resolves token IDs via
        convert_tokens_to_ids and adds them to the eos_token_ids set.
        """
        tokenizer = self._get_tokenizer()
        if not hasattr(tokenizer, "add_eos_token"):
            logger.debug("tokenizer does not support add_eos_token, skipping extra EOS registration")
            return

        # EOS tokens per model family.
        # These tokens mark the end of assistant reply in each model's chat template.
        _EXTRA_EOS_TOKENS: dict[str, list[str]] = {
            "glm": [
                "<|user|>", "<|observation|>", "<|endoftext|>",
            ],
            "qwen": [
                "<|im_end|>", "<|endoftext|>",
            ],
            "deepseek": [
                "<|end▁of▁sentence|>", "<｜end▁of▁sentence｜>",
            ],
            "kimi": [
                "<|im_end|>", "<|endoftext|>",
            ],
            "llama": [
                "<|eot_id|>",
            ],
            "mistral": [
                "</s>",
            ],
            # Gemma 3 / gemma3n: <end_of_turn> marks assistant reply end
            "gemma3": [
                "<end_of_turn>", "<start_of_turn>",
            ],
            # Gemma 4: <turn|> marks turn end (new control token system)
            # <|tool_response> marks the boundary where model expects tool results
            # <tool_call|> marks end of a tool call block
            # <channel|> marks end of thinking channel (reasoning)
            "gemma4": [
                "<turn|>", "<|turn>", "<|tool_response>", "<tool_call|>", "<channel|>",
            ],
        }

        name_lower = model_name.lower()
        registered = []

        # Gemma family needs special matching (gemma4 before gemma3)
        if "gemma" in name_lower:
            if "gemma4" in name_lower or "gemma-4" in name_lower:
                tokens = _EXTRA_EOS_TOKENS["gemma4"]
            else:
                tokens = _EXTRA_EOS_TOKENS["gemma3"]
            for token_str in tokens:
                try:
                    tokenizer.add_eos_token(token_str)
                    registered.append(token_str)
                except (ValueError, Exception):
                    pass
        else:
            for model_key, tokens in _EXTRA_EOS_TOKENS.items():
                if model_key.startswith("gemma"):
                    continue  # gemma handled above
                if model_key not in name_lower:
                    continue
                for token_str in tokens:
                    try:
                        tokenizer.add_eos_token(token_str)
                        registered.append(token_str)
                    except (ValueError, Exception):
                        # token not in vocabulary — skip (some quantized versions
                        # may lack certain special tokens)
                        pass
                break  # only match the first model type

        if registered:
            logger.info(
                "registered extra EOS tokens for model=%s: %s (total eos_token_ids=%d)",
                model_name, registered, len(tokenizer.eos_token_ids),
            )

    def _init_tool_parser(self) -> None:
        """根据 tokenizer chat_template 推断 tool parser 类型。"""
        try:
            from mlx_lm.tokenizer_utils import _infer_tool_parser
            tokenizer = self._get_tokenizer()
            if hasattr(tokenizer, "chat_template"):
                self._tool_parser_type = _infer_tool_parser(tokenizer.chat_template)
                if self._tool_parser_type:
                    self._tool_module = importlib.import_module(
                        f"mlx_lm.tool_parsers.{self._tool_parser_type}"
                    )
                    logger.info("tool parser detected: %s", self._tool_parser_type)
        except Exception as e:
            logger.debug("tool parser init skipped: %s", e)

    def _create_reasoning_parser(self) -> ReasoningParser | None:
        """为当前请求创建独立的 reasoning parser 实例。

        每次请求独立创建，避免流式推理中多个并发请求共享有状态对象导致竞争。
        """
        if self._reasoning_parser_name is None:
            return None
        return detect_reasoning_parser(self._model_name)

    # ------------------------------------------------------------------
    # Model chat format detection
    # ------------------------------------------------------------------

    def _detect_chat_format(self, model_name: str) -> str:
        """Detect the chat format variant for message pre-processing.

        Uses config.model_type (from HF model config) when available,
        falls back to model name heuristic.

        Returns:
            Chat format identifier: "gemma3", "gemma3n", "gemma4", "glm", or "".
        """
        # Prefer HF config.model_type for accurate detection
        if self._config and hasattr(self._config, "model_type"):
            mt = self._config.model_type
            if mt in ("gemma3", "gemma3n", "gemma4"):
                return mt

        # Fallback: model name heuristic
        name_lower = model_name.lower()
        if "gemma" in name_lower:
            if "gemma4" in name_lower or "gemma-4" in name_lower:
                return "gemma4"
            if "gemma3n" in name_lower or "gemma-3n" in name_lower:
                return "gemma3n"
            if "gemma3" in name_lower or "gemma-3" in name_lower:
                return "gemma3"
            # Unknown gemma variant — default to gemma3 style (safer)
            return "gemma3"
        if "glm" in name_lower:
            return "glm"
        return ""

    @staticmethod
    def _resolve_enable_thinking(request: ChatCompletionRequest) -> bool | None:
        """Resolve the effective enable_thinking flag from request fields.

        Priority: reasoning_effort (string) > enable_thinking (bool).
        - reasoning_effort set and != "none" → True
        - reasoning_effort == "none" → False
        - reasoning_effort not set → fall back to enable_thinking
        """
        if request.reasoning_effort is not None:
            return request.reasoning_effort.lower() != "none"
        return request.enable_thinking

    def _merge_stop_sequences(self, request_stop: list[str] | None) -> list[str]:
        """Merge request-level stop sequences with model default _stop_sequences.

        Returns a deduplicated list: model defaults + request extras.
        """
        if not request_stop:
            return list(self._stop_sequences)
        # Preserve order: model defaults first, then request extras (deduplicated)
        merged = list(self._stop_sequences)
        seen = set(merged)
        for s in request_stop:
            if s not in seen:
                merged.append(s)
                seen.add(s)
        return merged

    def _is_gemma_model(self) -> bool:
        """Check if the loaded model is a Gemma variant (gemma3/gemma3n/gemma4)."""
        return self._chat_format in ("gemma3", "gemma3n", "gemma4")

    # ------------------------------------------------------------------
    # prompt formatting
    # ------------------------------------------------------------------

    def _format_prompt(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        enable_thinking: bool | None = None,
    ) -> str:
        """Format prompt using chat template, dispatching LLM vs VLM backends.

        Gemma4 always uses our custom template (even when loaded as VLM) because
        mlx_vlm's apply_chat_template doesn't support Gemma4's tool_calls /
        tool_responses format — causing the model to never see tool results.
        """
        # Gemma4: always use the LLM tokenizer path with our injected template.
        # mlx_vlm's apply_chat_template does NOT render tool_responses correctly.
        is_gemma4_format = self._chat_format == "gemma4"

        if self._is_vlm and not is_gemma4_format:
            from mlx_vlm.prompt_utils import apply_chat_template
            return apply_chat_template(
                self._processor, self._config, messages,
                num_images=0, tools=tools,
            )

        # For Gemma4 VLM: use the inner tokenizer (which has our injected template)
        if is_gemma4_format and self._is_vlm:
            tokenizer = self._get_tokenizer()
            # Ensure inner tokenizer has our template
            inner = getattr(tokenizer, "_tokenizer", tokenizer)
            if not getattr(inner, "chat_template", None):
                logger.warning("gemma4 VLM: inner tokenizer missing chat_template, injecting now")
                inner.chat_template = _GEMMA4_CHAT_TEMPLATE
        else:
            tokenizer = self._get_tokenizer()

        kwargs: dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        if tools:
            kwargs["tools"] = tools
        if enable_thinking is not None:
            kwargs["enable_thinking"] = enable_thinking
        if self._is_gemma_model():
            kwargs["add_special_tokens"] = False
        formatted = tokenizer.apply_chat_template(messages, **kwargs)

        # Debug: validate the formatted prompt for Gemma4 FC scenarios
        if is_gemma4_format:
            has_tool_call = "<|tool_call>" in formatted
            has_tool_response = "tool_response" in formatted
            has_tool_decl = "<|tool>" in formatted
            input_has_tr = any(
                "tool_responses" in m and m["tool_responses"]
                for m in messages if isinstance(m, dict)
            )
            logger.debug(
                "gemma4 formatted_prompt: len=%d has_tool_decl=%s has_tool_call=%s "
                "has_tool_response=%s input_has_tool_responses=%s is_vlm=%s",
                len(formatted), has_tool_decl, has_tool_call,
                has_tool_response, input_has_tr, self._is_vlm,
            )
            if input_has_tr and not has_tool_response:
                logger.error(
                    "gemma4 CRITICAL: tool_responses in input messages but NOT in formatted prompt! "
                    "Model will not see tool results and may repeat the same tool_call. "
                    "prompt_preview=%s",
                    formatted[-500:],
                )
            logger.debug("gemma4 prompt_tail(1000): %s", formatted[-1000:])

        return formatted

    # ------------------------------------------------------------------
    # Non-streaming generation
    # ------------------------------------------------------------------

    def chat_complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        """Non-streaming Chat Completions with full observability.

        Pipeline: format prompt (CPU) → acquire lock → GPU inference → release lock
        → post-process (CPU). Captures lock_wait / prefill / decode timing.
        """
        import mlx.core as mx

        # --- Outside lock: prompt formatting (CPU-only) ---
        dict_messages = _messages_to_dict_list(request.messages, self._chat_format)
        dict_tools = _tools_to_dict_list(request.tools)
        enable_thinking = self._resolve_enable_thinking(request)
        formatted_prompt = self._format_prompt(
            dict_messages, dict_tools, enable_thinking=enable_thinking,
        )

        reasoning_parser = self._create_reasoning_parser()

        # FC scenario: clamp temperature + max_tokens
        temperature = request.temperature
        max_tokens = request.max_tokens
        if dict_tools and request.tool_choice != "none":
            ec = self._engine_config
            temperature = min(temperature, ec.tool_call_temperature)
            max_tokens = min(max_tokens, ec.tool_call_max_tokens)

        choices: list[ChatChoice] = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        tc_metrics: ToolCallMetrics | None = None
        infer_metrics = InferMetrics()

        for i in range(request.n):
            # Measure lock wait time
            lock_wait_start = _time.monotonic()
            with self._infer_lock:
                infer_metrics.lock_wait_ms = int((_time.monotonic() - lock_wait_start) * 1000)

                result_text, prompt_tks, gen_tks = self._generate_with_metrics(
                    formatted_prompt, infer_metrics,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=request.top_p,
                )
            mx.clear_cache()

            # --- Post-processing (CPU-only) ---
            # Debug: log raw model output before any processing
            logger.debug(
                "raw model output (len=%d): %s",
                len(result_text), result_text[:500],
            )
            result_text = _truncate_at_stop(result_text, self._merge_stop_sequences(request.stop))
            # First cleanup: remove generic special tokens but preserve Gemma4
            # tool_call tokens (needed by Gemma4Extractor for parsing)
            result_text = _clean_special_tokens(result_text)

            reasoning_text = None
            content_text = result_text
            if reasoning_parser:
                reasoning_text, parsed_content = reasoning_parser.extract_reasoning(result_text)
                content_text = parsed_content if parsed_content is not None else ""

            parse_result = self._parse_tool_calls(
                content_text, dict_tools, request.tool_choice, formatted_prompt, max_tokens,
            )
            # Post-parse cleanup: now safe to remove Kimi + Gemma4 tool tokens
            content_text = _clean_special_tokens(
                parse_result.remaining_text,
                include_tool_tokens=True,
                include_gemma4_tokens=True,
            )
            tool_calls = parse_result.calls
            tc_metrics = parse_result.metrics
            finish_reason = "tool_calls" if tool_calls else "stop"

            choices.append(
                ChatChoice(
                    index=i,
                    message=ChatMessage(
                        role="assistant",
                        content=content_text if content_text else None,
                        reasoning_content=reasoning_text,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=finish_reason,
                )
            )
            total_prompt_tokens = prompt_tks
            total_completion_tokens += gen_tks

        # Compute total_ms and emit metrics
        infer_metrics.total_ms = infer_metrics.lock_wait_ms + infer_metrics.prefill_ms + infer_metrics.decode_ms
        infer_metrics.log_summary(request.request_id)

        reasoning_tokens = self._count_reasoning_tokens(choices)
        details = CompletionTokensDetails(reasoning_tokens=reasoning_tokens) if reasoning_tokens > 0 else None
        usage = UsageStats(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            completion_tokens_details=details,
        )
        result = ChatCompletionResult(choices=choices, usage=usage, tool_call_metrics=tc_metrics)
        result.infer_metrics = infer_metrics  # type: ignore[attr-defined]
        return result

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    def stream_chat_complete(
        self, request: ChatCompletionRequest,
    ) -> Generator[ChatCompletionChunkResult, None, None]:
        """Streaming Chat Completions with adaptive prefill + observability.

        Pipeline: format (CPU) → lock wait → prefill+decode (GPU stream) → unlock
        → tool_calls parse (CPU). First chunk boundary splits prefill/decode timing.
        """
        import mlx.core as mx

        # --- Outside lock: prompt formatting (CPU-only) ---
        dict_messages = _messages_to_dict_list(request.messages, self._chat_format)
        dict_tools = _tools_to_dict_list(request.tools)
        enable_thinking = self._resolve_enable_thinking(request)
        formatted_prompt = self._format_prompt(
            dict_messages, dict_tools, enable_thinking=enable_thinking,
        )

        reasoning_parser = self._create_reasoning_parser()

        # FC scenario: clamp temperature + max_tokens
        temperature = request.temperature
        max_tokens = request.max_tokens
        if dict_tools and request.tool_choice != "none":
            ec = self._engine_config
            temperature = min(temperature, ec.tool_call_temperature)
            max_tokens = min(max_tokens, ec.tool_call_max_tokens)

        # Merge request-level stop with model default stop sequences
        merged_stop = self._merge_stop_sequences(request.stop)

        full_text = ""
        previous_text = ""
        last_usage = UsageStats()
        infer_metrics = InferMetrics()

        try:
            # Measure lock wait time
            lock_wait_start = _time.monotonic()
            with self._infer_lock:
                infer_metrics.lock_wait_ms = int((_time.monotonic() - lock_wait_start) * 1000)

                token_iterator = self._stream_generate(
                    formatted_prompt, metrics=infer_metrics,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=request.top_p,
                )

                first_token = True
                prefill_start = _time.monotonic()

                for chunk in token_iterator:
                    if chunk is None or not hasattr(chunk, "text"):
                        continue

                    delta_text = chunk.text

                    # First token marks end of prefill phase
                    if first_token and delta_text:
                        infer_metrics.prefill_ms = int((_time.monotonic() - prefill_start) * 1000)
                        first_token = False

                    full_text += delta_text

                    # Stop sequence detection: truncate and terminate immediately
                    stop_hit = False
                    if merged_stop:
                        for stop_seq in merged_stop:
                            stop_pos = full_text.find(stop_seq)
                            if stop_pos != -1:
                                truncated_full = full_text[:stop_pos]
                                prev_len = len(full_text) - len(delta_text)
                                delta_text = truncated_full[prev_len:] if stop_pos > prev_len else ""
                                full_text = truncated_full
                                stop_hit = True
                                logger.debug("stream stop sequence detected: '%s'", stop_seq)
                                break

                    last_usage = UsageStats(
                        prompt_tokens=getattr(chunk, "prompt_tokens", 0),
                        completion_tokens=getattr(chunk, "generation_tokens", 0),
                        total_tokens=(
                            getattr(chunk, "prompt_tokens", 0)
                            + getattr(chunk, "generation_tokens", 0)
                        ),
                    )

                    if reasoning_parser:
                        delta_msg = reasoning_parser.extract_reasoning_streaming(
                            previous_text, full_text, delta_text,
                        )
                        previous_text = full_text

                        if delta_msg is None:
                            continue

                        content_part = _clean_special_tokens(
                            delta_msg.content, include_gemma4_tokens=True,
                        ) if delta_msg.content else None
                        reasoning_part = delta_msg.reasoning

                        if not content_part and not reasoning_part:
                            continue

                        yield ChatCompletionChunkResult(
                            choices=[
                                StreamChoice(
                                    index=0,
                                    delta=StreamDelta(
                                        content=content_part,
                                        reasoning_content=reasoning_part,
                                    ),
                                )
                            ]
                        )
                    else:
                        # Clean for client display (including Gemma4 tool tokens)
                        # but full_text retains them for post-stream tool_call parsing
                        cleaned = _clean_special_tokens(delta_text, include_gemma4_tokens=True)
                        if cleaned:
                            yield ChatCompletionChunkResult(
                                choices=[
                                    StreamChoice(
                                        index=0,
                                        delta=StreamDelta(content=cleaned),
                                    )
                                ]
                            )

                    if stop_hit:
                        break

                # Capture decode phase timing
                total_gpu_ms = int((_time.monotonic() - prefill_start) * 1000)
                infer_metrics.decode_ms = max(0, total_gpu_ms - infer_metrics.prefill_ms)

            # --- Outside lock: tool_calls parsing + final chunk (CPU) ---
            if reasoning_parser:
                _, content_for_tools = reasoning_parser.extract_reasoning(full_text)
                content_for_tools = content_for_tools or ""
            else:
                content_for_tools = full_text

            parse_result = self._parse_tool_calls(
                content_for_tools, dict_tools, request.tool_choice, formatted_prompt, max_tokens,
            )
            tool_calls = parse_result.calls
            finish_reason = "tool_calls" if tool_calls else "stop"

            final_delta = StreamDelta()
            if tool_calls:
                final_delta.tool_calls = tool_calls

            # Finalize metrics
            infer_metrics.prompt_tokens = last_usage.prompt_tokens
            infer_metrics.completion_tokens = last_usage.completion_tokens
            infer_metrics.total_ms = infer_metrics.lock_wait_ms + infer_metrics.prefill_ms + infer_metrics.decode_ms
            infer_metrics.log_summary(request.request_id)

            yield ChatCompletionChunkResult(
                choices=[
                    StreamChoice(
                        index=0,
                        delta=final_delta,
                        finish_reason=finish_reason,
                    )
                ],
                usage=last_usage,
                infer_metrics=infer_metrics,  # type: ignore[call-arg]
            )
        finally:
            mx.clear_cache()

    # ------------------------------------------------------------------
    # Backend: generate / stream_generate with adaptive prefill
    # ------------------------------------------------------------------

    @staticmethod
    def _make_lm_sampler(temperature: float, top_p: float) -> Any:
        """Build mlx_lm sampler callback (mlx_lm >= 0.31 API)."""
        from mlx_lm.sample_utils import make_sampler
        return make_sampler(temp=temperature, top_p=top_p)

    def _estimate_prompt_tokens(self, prompt: str) -> int:
        """Fast prompt token count estimate for adaptive prefill decisions.

        Uses the tokenizer CPU pool to avoid blocking GPU. Falls back to
        a rough char-based estimate if tokenization fails.
        """
        try:
            return self._count_tokens_on_cpu(prompt)
        except Exception:
            # Rough fallback: ~3.5 chars per token for English/Chinese mix
            return len(prompt) // 4

    def _resolve_prefill_step(self, prompt_tokens: int) -> int:
        """Resolve the effective prefill_step_size for this request.

        Short prompts → 0 (single-shot eval, skip chunked prefill).
        Long prompts → adaptive step based on prompt length + available memory.
        """
        ec = self._engine_config
        if ec.prefill_step_size <= 0:
            return 0

        from service.memory_guard import get_available_memory_gb
        available_mem = get_available_memory_gb()
        step = _compute_adaptive_prefill_step(prompt_tokens, ec.prefill_step_size, available_mem)
        if step > 0:
            logger.debug(
                "adaptive prefill: prompt_tokens=%d available_mem=%.1fGB → step=%d (base=%d)",
                prompt_tokens, available_mem, step, ec.prefill_step_size,
            )
        return step

    def _generate_with_metrics(
        self, prompt: str, metrics: InferMetrics, **kwargs: Any,
    ) -> tuple[str, int, int]:
        """Non-streaming generation with full timing metrics.

        Wraps _stream_generate, tracks prefill/decode phases via the first
        chunk boundary (first chunk = prefill done).

        Returns:
            (text, prompt_tokens, generation_tokens)
        """
        full_text = ""
        prompt_tokens = 0
        generation_tokens = 0
        first_token = True
        prefill_start = _time.monotonic()

        for chunk in self._stream_generate(prompt, metrics=metrics, **kwargs):
            if chunk is None:
                continue
            if first_token and hasattr(chunk, "text") and chunk.text:
                # First token marks end of prefill phase
                metrics.prefill_ms = int((_time.monotonic() - prefill_start) * 1000)
                first_token = False

            full_text += getattr(chunk, "text", "")
            prompt_tokens = getattr(chunk, "prompt_tokens", prompt_tokens)
            generation_tokens = getattr(chunk, "generation_tokens", generation_tokens)

        # Decode phase = total GPU time - prefill time
        total_gpu_ms = int((_time.monotonic() - prefill_start) * 1000)
        metrics.decode_ms = max(0, total_gpu_ms - metrics.prefill_ms)
        metrics.prompt_tokens = prompt_tokens
        metrics.completion_tokens = generation_tokens
        return full_text, prompt_tokens, generation_tokens

    def _stream_generate(self, prompt: str, metrics: InferMetrics | None = None, **kwargs: Any) -> Any:
        """Dispatch to LLM/VLM stream_generate with KV Cache + adaptive prefill.

        Args:
            prompt: Formatted prompt string.
            metrics: Optional InferMetrics to record prefill_step_size used.
            **kwargs: temperature, max_tokens, top_p.
        """
        temperature = kwargs.get("temperature", 1.0)
        max_tokens = kwargs.get("max_tokens", 512)
        top_p = kwargs.get("top_p", 1.0)

        if self._is_vlm:
            from mlx_vlm.generate import stream_generate
            return stream_generate(
                model=self._model,
                processor=self._processor,
                prompt=prompt,
                image=[],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )

        from mlx_lm import stream_generate

        extra_kwargs: dict[str, Any] = {}
        ec = self._engine_config

        # KV Cache: RotatingKVCache for memory-bounded inference
        if ec.use_paged_cache and ec.max_kv_size > 0:
            try:
                from mlx_lm.models.cache import RotatingKVCache
                cache_kwargs: dict[str, Any] = {"max_size": ec.max_kv_size}
                if ec.kv_bits > 0:
                    cache_kwargs["kv_bits"] = ec.kv_bits
                    cache_kwargs["kv_group_size"] = ec.kv_group_size
                extra_kwargs["kv_cache"] = RotatingKVCache(**cache_kwargs)
            except ImportError:
                logger.warning("RotatingKVCache not available, using default cache")

        # Adaptive prefill: compute optimal step_size per request
        prompt_tokens_est = self._estimate_prompt_tokens(prompt)
        step = self._resolve_prefill_step(prompt_tokens_est)
        if step > 0:
            extra_kwargs["prefill_step_size"] = step
        if metrics is not None:
            metrics.prefill_step_size = step
            metrics.prompt_length = prompt_tokens_est

        return stream_generate(
            model=self._model,
            tokenizer=self._processor,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=self._make_lm_sampler(temperature, top_p),
            **extra_kwargs,
        )

    # ------------------------------------------------------------------
    # tool calls 解析（配置驱动）
    # ------------------------------------------------------------------

    def _parse_tool_calls(
        self,
        text: str,
        tools: list[dict] | None,
        tool_choice: str = "auto",
        prompt: str = "",
        max_tokens: int = 512,
    ) -> ToolCallParseResult:
        """配置驱动的 Function Call 解析。

        根据 EngineConfig.tool_call_strategy 选择解析策略：
        - "parser_only":              仅 ToolCallParser 状态机解析 + schema 校验
        - "outlines_only":            仅 outlines-mlx 约束解码
        - "parser_fallback_outlines": 先 parser，失败后 fallback outlines-mlx

        自动传递 model_type 以支持 GLM XML / Kimi token 格式。
        """
        if not tools or tool_choice == "none":
            return ToolCallParseResult(remaining_text=text)

        dict_tools = ToolCallParser.tools_to_dict_list(tools) if tools and not isinstance(tools[0], dict) else tools
        strategy = self._engine_config.tool_call_strategy

        if strategy == "outlines_only":
            return self._parse_via_outlines(prompt, dict_tools, max_tokens)

        # parser_only 或 parser_fallback_outlines: 先走 ToolCallParser
        result = self._tc_parser.parse(text, dict_tools, tool_choice, model_type=self._model_type)

        # parser_fallback_outlines: parser 失败时 fallback outlines-mlx
        if strategy == "parser_fallback_outlines" and not result.metrics.tool_call_success:
            if self._outlines_provider.available:
                logger.info("ToolCallParser failed, falling back to outlines-mlx constrained decoding")
                outlines_result = self._parse_via_outlines(prompt, dict_tools, max_tokens)
                outlines_result.metrics.tool_call_retried = True
                return outlines_result
            else:
                logger.debug("outlines-mlx not available for fallback")

        return result

    def _parse_via_outlines(
        self,
        prompt: str,
        tools: list[dict],
        max_tokens: int = 512,
    ) -> ToolCallParseResult:
        """Generate tool_call via outlines-mlx constrained decoding."""
        start_ms = int(_time.monotonic() * 1000)

        schema = ToolCallParser.build_tool_call_json_schema(tools)
        raw = self._outlines_provider.constrained_generate(prompt, schema, max_tokens)

        metrics = ToolCallMetrics()
        if not raw:
            metrics.tool_call_success = False
            metrics.tool_call_parse_ms = int(_time.monotonic() * 1000) - start_ms
            return ToolCallParseResult(metrics=metrics)

        # 用 ToolCallParser 校验 outlines 生成的结果
        result = self._tc_parser.parse(raw, tools)
        result.metrics.tool_call_parse_ms = int(_time.monotonic() * 1000) - start_ms
        return result

    # ------------------------------------------------------------------
    # reasoning tokens 精确统计
    # ------------------------------------------------------------------

    def _count_reasoning_tokens(self, choices: list[ChatChoice]) -> int:
        """使用 tokenizer 在 CPU 线程池中对 reasoning_content 做精确 token 计数。

        替代原先 len(text)//4 的粗略估算，利用 _count_tokens_on_cpu 方法
        将 tokenize 操作卸载到 CPU 线程池，避免占用 GPU。
        """
        total = 0
        for c in choices:
            if c.message and c.message.reasoning_content:
                total += self._count_tokens_on_cpu(c.message.reasoning_content)
        return total
