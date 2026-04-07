"""MLX 推理引擎 — 适用于 Apple Silicon (M系列) Mac。

自动区分纯语言模型 (LLM) 与视觉语言模型 (VLM)：
  - LLM: 使用 mlx_lm（安装: pip install mlx-lm）
  - VLM: 使用 mlx_vlm（安装: pip install mlx-vlm）

支持:
  - 非流式 / 流式
  - tools（通过 chat_template 推断）
  - reasoning_content（自动检测 DeepSeek R1 / Qwen3 等推理模型）
  - n（降级为循环）

性能特性（由 EngineConfig 控制）:
  - Tokenizer CPU 线程池卸载：编码/解码在独立 CPU 线程池执行，不占 GPU
  - KV Cache 分页管理：通过 RotatingKVCache 控制显存峰值
  - Prefill 分步：大 prompt 按 step_size 分批 eval，防止 Metal OOM
  - 推理串行保护：MLX Metal 有线程安全限制，默认全流程持锁
"""

from __future__ import annotations

import gc
import importlib
import json
import logging
import re
import threading
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
        "<turn|>", "<|turn>", "<|tool_response>",
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
# Filter residual special tokens from model output
_SPECIAL_TOKENS_RE = re.compile(
    r"<\|im_end\|>|<\|im_start\|>|<\|endoftext\|>|"
    r"<\|end\|>|<\|eot_id\|>|<\|start_header_id\|>|<\|end_header_id\|>|"
    r"<\|observation\|>|<\|user\|>|<\|assistant\|>|"
    r"<\|end_of_text\|>|<\|end▁of▁sentence\|>|<｜end▁of▁sentence｜>|"
    # Gemma 3 control tokens
    r"<end_of_turn>|<start_of_turn>|"
    # Gemma 4 control tokens
    r"<\|turn>|<turn\|>|"
    # Gemma 4 tool call / tool response control tokens
    r'<\|tool_call>|<tool_call\|>|<\|tool_response>|<tool_response\|>|'
    r'<\|tool>|<tool\|>|<\|"\|>|'
    r"</s>|<s>|<pad>|\[PAD\]|\[SEP\]|\[CLS\]"
)

# Kimi tool_call 定界 token（tool_call 解析完成后清理）
_KIMI_TOOL_TOKENS_RE = re.compile(
    r"<\|tool_call_begin\|>|<\|tool_call_end\|>|"
    r"<\|tool_calls_section_begin\|>|<\|tool_calls_section_end\|>|"
    r"<\|tool_call_argument_begin\|>"
)


def _clean_special_tokens(text: str, include_tool_tokens: bool = False) -> str:
    """移除模型输出中的特殊 token。"""
    result = _SPECIAL_TOKENS_RE.sub("", text)
    if include_tool_tokens:
        result = _KIMI_TOOL_TOKENS_RE.sub("", result)
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

    Historical reasoning_content is wrapped in <think>...</think> and
    prepended to content, so the model can "see" prior reasoning in
    multi-turn conversations.

    Model-specific adaptations:
      - GLM: maps role="tool" to "observation".
      - Gemma 3 (gemma3/gemma3n): no system role support — system messages
        are merged into the first user message content.
      - Gemma 4: supports system role natively, no special handling needed.
    """
    result = []

    # Gemma 3 pre-processing: collect system content to merge into first user msg
    is_gemma3 = model_type in ("gemma3", "gemma3n")
    system_content_for_merge = ""
    if is_gemma3:
        for m in messages:
            if m.role == "system" and m.content:
                system_content_for_merge += m.content + "\n\n"

    first_user_seen = False
    for m in messages:
        role = m.role

        # Gemma 3: skip system messages (already collected for merge)
        if is_gemma3 and role == "system":
            continue

        # GLM: tool results use "observation" role
        if model_type == "glm" and role == "tool":
            role = "observation"

        msg: dict[str, Any] = {"role": role, "content": m.content or ""}

        # Gemma 3: merge system content into first user message
        if is_gemma3 and role == "user" and not first_user_seen and system_content_for_merge:
            msg["content"] = system_content_for_merge + (m.content or "")
            first_user_seen = True
        elif role == "user":
            first_user_seen = True

        # Prepend reasoning_content from historical assistant messages
        if m.role == "assistant" and m.reasoning_content:
            msg["content"] = f"<think>{m.reasoning_content}</think>{m.content or ''}"
        if m.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function_name, "arguments": tc.function_arguments},
                }
                for tc in m.tool_calls
            ]
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        if m.name:
            msg["name"] = m.name
        result.append(msg)
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

            # 向 tokenizer 注册模型特有的 stop token 为 EOS token。
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
            "gemma4": [
                "<turn|>", "<|turn>", "<|tool_response>", "<tool_call|>",
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

        For Gemma 3/4 models, follows mlx_vlm convention: set
        add_special_tokens=False when the processor has a chat_template,
        preventing duplicate BOS tokens.
        """
        if self._is_vlm:
            from mlx_vlm.prompt_utils import apply_chat_template
            return apply_chat_template(
                self._processor, self._config, messages,
                num_images=0, tools=tools,
            )
        tokenizer = self._get_tokenizer()
        kwargs: dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        if tools:
            kwargs["tools"] = tools
        # Some models (e.g. Qwen3) support enable_thinking in chat template
        if enable_thinking is not None:
            kwargs["enable_thinking"] = enable_thinking
        # Gemma 3/4: set add_special_tokens=False when using chat_template
        # to prevent duplicate BOS tokens (follows mlx_vlm convention)
        if self._is_gemma_model():
            kwargs["add_special_tokens"] = False
        return tokenizer.apply_chat_template(messages, **kwargs)

    # ------------------------------------------------------------------
    # 非流式生成
    # ------------------------------------------------------------------

    def chat_complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        """非流式 Chat Completions。

        优化策略：
          - prompt 格式化在锁外执行（纯 CPU 操作）
          - 推理锁保护 GPU 串行执行
          - 后处理（reasoning 解析、tool_calls 提取）在锁外执行
          - 不在热路径触发 gc.collect，仅清理 Metal cache
          - FC 场景自动降温 + 限制 max_tokens（由 EngineConfig 控制）
        """
        import mlx.core as mx

        # --- Outside lock: prompt formatting (CPU-only) ---
        dict_messages = _messages_to_dict_list(request.messages, self._chat_format)
        dict_tools = _tools_to_dict_list(request.tools)
        formatted_prompt = self._format_prompt(
            dict_messages, dict_tools, enable_thinking=request.enable_thinking,
        )

        reasoning_parser = self._create_reasoning_parser()

        # FC 场景参数调整
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

        for i in range(request.n):
            # --- 锁内：GPU 推理（Metal 串行保护）---
            with self._infer_lock:
                result_text, prompt_tks, gen_tks = self._generate_with_stats(
                    formatted_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=request.top_p,
                )
            # 仅清理 Metal cache，不触发 GC（避免热路径延迟）
            mx.clear_cache()

            # --- 锁外：后处理（纯 CPU 操作）---
            # 第零阶段：按模型 stop 序列硬截断，防止续写下一轮对话
            result_text = _truncate_at_stop(result_text, self._stop_sequences)
            # 第一阶段清理：移除通用特殊 token（保留 Kimi tool_call 定界符）
            result_text = _clean_special_tokens(result_text)

            reasoning_text = None
            content_text = result_text
            if reasoning_parser:
                reasoning_text, parsed_content = reasoning_parser.extract_reasoning(result_text)
                content_text = parsed_content if parsed_content is not None else ""

            # 配置驱动的 tool_call 解析（传递 model_type）
            parse_result = self._parse_tool_calls(
                content_text, dict_tools, request.tool_choice, formatted_prompt, max_tokens,
            )
            # 第二阶段清理：tool_call 解析完成后清理 Kimi 定界 token
            content_text = _clean_special_tokens(
                parse_result.remaining_text, include_tool_tokens=True,
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

        # 精确统计 reasoning tokens（在 CPU 线程池中 tokenize）
        reasoning_tokens = self._count_reasoning_tokens(choices)
        details = CompletionTokensDetails(reasoning_tokens=reasoning_tokens) if reasoning_tokens > 0 else None
        usage = UsageStats(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            completion_tokens_details=details,
        )
        return ChatCompletionResult(choices=choices, usage=usage, tool_call_metrics=tc_metrics)

    # ------------------------------------------------------------------
    # 流式生成
    # ------------------------------------------------------------------

    def stream_chat_complete(
        self, request: ChatCompletionRequest,
    ) -> Generator[ChatCompletionChunkResult, None, None]:
        """流式 Chat Completions。

        优化策略：
          - prompt 格式化在锁外执行（纯 CPU）
          - 推理锁保护整个 stream（MLX Metal 线程安全约束）
          - tool_calls 解析在锁释放后执行
          - 不在热路径触发 gc.collect
          - FC 场景自动降温 + 限制 max_tokens
        """
        import mlx.core as mx

        # --- Outside lock: prompt formatting (CPU-only) ---
        dict_messages = _messages_to_dict_list(request.messages, self._chat_format)
        dict_tools = _tools_to_dict_list(request.tools)
        formatted_prompt = self._format_prompt(
            dict_messages, dict_tools, enable_thinking=request.enable_thinking,
        )

        reasoning_parser = self._create_reasoning_parser()

        # FC 场景参数调整
        temperature = request.temperature
        max_tokens = request.max_tokens
        if dict_tools and request.tool_choice != "none":
            ec = self._engine_config
            temperature = min(temperature, ec.tool_call_temperature)
            max_tokens = min(max_tokens, ec.tool_call_max_tokens)

        full_text = ""
        previous_text = ""
        last_usage = UsageStats()

        try:
            # --- 锁内：GPU 推理 stream（Metal 串行保护）---
            with self._infer_lock:
                token_iterator = self._stream_generate(
                    formatted_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=request.top_p,
                )

                for chunk in token_iterator:
                    if chunk is None or not hasattr(chunk, "text"):
                        continue

                    delta_text = chunk.text
                    full_text += delta_text

                    # 检测 stop 序列: 一旦生成到 stop token 立即截断并终止
                    stop_hit = False
                    if self._stop_sequences:
                        for stop_seq in self._stop_sequences:
                            stop_pos = full_text.find(stop_seq)
                            if stop_pos != -1:
                                # 计算截断后 full_text 的长度
                                truncated_full = full_text[:stop_pos]
                                # 重新计算 delta_text: 只保留截断范围内的增量
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

                        content_part = _clean_special_tokens(delta_msg.content) if delta_msg.content else None
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
                        cleaned = _clean_special_tokens(delta_text)
                        if cleaned:
                            yield ChatCompletionChunkResult(
                                choices=[
                                    StreamChoice(
                                        index=0,
                                        delta=StreamDelta(content=cleaned),
                                    )
                                ]
                            )

                    # stop 序列命中后终止 stream
                    if stop_hit:
                        break

            # --- 锁外：tool_calls 解析 + 最终 chunk（纯 CPU）---
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

            yield ChatCompletionChunkResult(
                choices=[
                    StreamChoice(
                        index=0,
                        delta=final_delta,
                        finish_reason=finish_reason,
                    )
                ],
                usage=last_usage,
            )
        finally:
            # 仅清理 Metal cache，不触发 GC（避免热路径延迟）
            mx.clear_cache()
            logger.debug("stream generation finished, Metal cache cleared")

    # ------------------------------------------------------------------
    # 后端适配：统一封装 generate / stream_generate
    # ------------------------------------------------------------------

    @staticmethod
    def _make_lm_sampler(temperature: float, top_p: float) -> Any:
        """构建 mlx_lm generate_step 所需的 sampler 回调。

        mlx_lm >= 0.31 不再接受 temperature/top_p 作为直接参数，
        需要通过 make_sampler 创建采样函数传入 sampler 参数。
        """
        from mlx_lm.sample_utils import make_sampler
        return make_sampler(temp=temperature, top_p=top_p)

    def _generate_with_stats(self, prompt: str, **kwargs: Any) -> tuple[str, int, int]:
        """非流式生成：通过 stream_generate 收集完整文本 + token 统计。

        Returns:
            (text, prompt_tokens, generation_tokens)
        """
        full_text = ""
        prompt_tokens = 0
        generation_tokens = 0
        for chunk in self._stream_generate(prompt, **kwargs):
            if chunk is None:
                continue
            full_text += getattr(chunk, "text", "")
            prompt_tokens = getattr(chunk, "prompt_tokens", prompt_tokens)
            generation_tokens = getattr(chunk, "generation_tokens", generation_tokens)
        logger.debug(
            "generate_with_stats: prompt_tokens=%d generation_tokens=%d",
            prompt_tokens, generation_tokens,
        )
        return full_text, prompt_tokens, generation_tokens

    def _stream_generate(self, prompt: str, **kwargs: Any) -> Any:
        """根据模型类型调用对应的 stream_generate，传入 KV Cache 和 prefill 配置。"""
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

        # 构建 KV Cache 和 prefill 参数
        extra_kwargs: dict[str, Any] = {}
        ec = self._engine_config

        # KV Cache 分页管理：使用 RotatingKVCache 控制显存峰值
        if ec.use_paged_cache and ec.max_kv_size > 0:
            try:
                from mlx_lm.models.cache import RotatingKVCache
                cache_kwargs: dict[str, Any] = {"max_size": ec.max_kv_size}
                if ec.kv_bits > 0:
                    cache_kwargs["kv_bits"] = ec.kv_bits
                    cache_kwargs["kv_group_size"] = ec.kv_group_size
                extra_kwargs["kv_cache"] = RotatingKVCache(**cache_kwargs)
                logger.debug(
                    "using RotatingKVCache: max_size=%d kv_bits=%d",
                    ec.max_kv_size, ec.kv_bits,
                )
            except ImportError:
                logger.warning("RotatingKVCache not available in current mlx_lm version, using default cache")

        # Prefill 分步大小：防止大 prompt 单次 eval 导致 Metal OOM
        if ec.prefill_step_size > 0:
            extra_kwargs["prefill_step_size"] = ec.prefill_step_size

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
        """通过 outlines-mlx 约束解码生成 tool_call。"""
        import time as _time
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
