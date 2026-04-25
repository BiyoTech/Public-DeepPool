"""gRPC 推理服务 — 严格对齐 OpenAI Chat Completions API。

提供两个 RPC：
  - ChatCompletion:       非流式，返回完整 ChatCompletionResponse
  - ChatCompletionStream: 服务端流式，逐 chunk 返回 ChatCompletionChunk

协议层负责 proto ↔ engine 数据结构的双向转换，
引擎层专注 Chat Completions 语义的推理实现。

多模型路由：Servicer 持有 ServiceManager 引用，
根据 request.model 字段通过 manager.get_or_load_engine() 获取对应引擎。

兼容: DeepSeek R1 (reasoning_content) / Qwen3 (<think>) 等推理模型。
"""

from __future__ import annotations

import logging
import time
import uuid
from concurrent import futures
from typing import TYPE_CHECKING

import grpc

from engine.base import (
    ChatCompletionRequest,
    ChatMessage as EngineChatMessage,
    CompletionTokensDetails,
    ContentPart,
    FunctionDef,
    LLMEngine,
    ResponseFormat,
    ToolCallResult,
    ToolDef,
    UsageStats,
)
from generated import llm_infer_pb2, llm_infer_pb2_grpc

if TYPE_CHECKING:
    from service.manager import ServiceManager

logger = logging.getLogger(__name__)


def _record_stats(**kwargs) -> None:
    """延迟导入 statistics 模块并记录推理请求，避免循环导入。"""
    from service.statistics import InferRecord, get_statistics_db
    get_statistics_db().record(InferRecord(**kwargs))


# ─────────────────────────────────────────────────
# Proto ↔ Engine 数据结构转换
# ─────────────────────────────────────────────────

def _parse_multipart_content(raw_content: str) -> list[ContentPart] | str:
    """尝试将 content 字符串解析为多部分内容数组（视觉理解等多模态请求）。

    当 Gateway 转发多模态请求到 DeepNode 时，会将原始 JSON 数组作为 content 字符串传递。
    此函数检测 content 是否为 JSON 数组格式，如果是则解析为 ContentPart 列表。
    否则返回原始字符串（纯文本，向后兼容）。
    """
    if not raw_content or not raw_content.startswith("["):
        return raw_content
    try:
        import json
        parts = json.loads(raw_content)
        if not isinstance(parts, list):
            return raw_content
        result = []
        for part in parts:
            if not isinstance(part, dict) or "type" not in part:
                return raw_content  # 不是有效的 content parts 格式，回退到纯文本
            cp = ContentPart(type=part["type"])
            if part["type"] == "text":
                cp.text = part.get("text", "")
            elif part["type"] == "image_url":
                cp.image_url = part.get("image_url", {})
            result.append(cp)
        return result
    except (json.JSONDecodeError, TypeError, KeyError):
        return raw_content


def _proto_messages_to_engine(proto_msgs) -> list[EngineChatMessage]:
    """Convert proto ChatMessage list to engine ChatMessage list.

    Supports multi-part content (vision requests): when the content field
    contains a JSON array string (forwarded by Gateway for multi-modal requests),
    it is parsed into a list of ContentPart objects.
    """
    result = []
    for pm in proto_msgs:
        tool_calls = None
        if pm.tool_calls:
            tool_calls = [
                ToolCallResult(
                    id=tc.id,
                    type=tc.type,
                    function_name=tc.function.name,
                    function_arguments=tc.function.arguments,
                )
                for tc in pm.tool_calls
            ]

        # Parse content: detect multi-part JSON array for vision/multi-modal requests.
        raw_content = pm.content if pm.HasField("content") else None
        if raw_content is not None:
            content = _parse_multipart_content(raw_content)
        else:
            content = None

        msg = EngineChatMessage(
            role=pm.role,
            content=content,
            name=pm.name if pm.HasField("name") else None,
            tool_calls=tool_calls,
            tool_call_id=pm.tool_call_id if pm.HasField("tool_call_id") else None,
            reasoning_content=pm.reasoning_content if pm.HasField("reasoning_content") else None,
        )
        result.append(msg)

    # Debug: log message structure for tracing FC issues
    logger.debug(
        "proto_to_engine: %d messages [%s]",
        len(result),
        ", ".join(
            f"{m.role}(tc={len(m.tool_calls) if m.tool_calls else 0},"
            f"tcid={m.tool_call_id or '-'},name={m.name or '-'},"
            f"content_len={len(m.content) if m.content else 0})"
            for m in result
        ),
    )
    return result


def _proto_tools_to_engine(proto_tools) -> list[ToolDef] | None:
    """将 proto Tool 列表转换为引擎层 ToolDef。"""
    if not proto_tools:
        return None
    return [
        ToolDef(
            type=t.type or "function",
            function=FunctionDef(
                name=t.function.name,
                description=t.function.description if t.function.HasField("description") else "",
                parameters=t.function.parameters,
            ),
        )
        for t in proto_tools
    ]


def _proto_request_to_engine(req) -> ChatCompletionRequest:
    """将 proto ChatCompletionRequest 转换为引擎层请求。"""
    resp_format = None
    if req.HasField("response_format"):
        resp_format = ResponseFormat(
            type=req.response_format.type or "text",
            json_schema=(
                req.response_format.json_schema
                if req.response_format.HasField("json_schema")
                else None
            ),
        )
    return ChatCompletionRequest(
        messages=_proto_messages_to_engine(req.messages),
        temperature=req.temperature or 1.0,
        top_p=req.top_p or 1.0,
        n=req.n or 1,
        max_tokens=req.max_tokens or 256,
        stop=list(req.stop) if req.stop else None,
        presence_penalty=req.presence_penalty,
        frequency_penalty=req.frequency_penalty,
        tools=_proto_tools_to_engine(req.tools),
        tool_choice=req.tool_choice or "auto",
        response_format=resp_format,
        seed=req.seed if req.HasField("seed") else None,
        logprobs=req.logprobs,
        top_logprobs=req.top_logprobs if req.HasField("top_logprobs") else None,
        user=req.user,
        request_id=req.request_id,
        enable_thinking=req.enable_thinking if req.HasField("enable_thinking") else None,
        reasoning_effort=req.reasoning_effort if req.HasField("reasoning_effort") else None,
    )


def _engine_message_to_proto(msg: EngineChatMessage) -> llm_infer_pb2.ChatMessage:
    """将引擎层 ChatMessage 转换为 proto ChatMessage。"""
    proto_msg = llm_infer_pb2.ChatMessage(role=msg.role)
    if msg.content is not None:
        proto_msg.content = msg.content
    if msg.name:
        proto_msg.name = msg.name
    if msg.tool_call_id:
        proto_msg.tool_call_id = msg.tool_call_id
    if msg.reasoning_content is not None:
        proto_msg.reasoning_content = msg.reasoning_content
    if msg.tool_calls:
        for tc in msg.tool_calls:
            proto_msg.tool_calls.append(
                llm_infer_pb2.ToolCall(
                    id=tc.id,
                    type=tc.type,
                    function=llm_infer_pb2.FunctionCallDetail(
                        name=tc.function_name,
                        arguments=tc.function_arguments,
                    ),
                )
            )
    return proto_msg


def _engine_logprobs_to_proto(lp) -> llm_infer_pb2.ChoiceLogprobs | None:
    """将引擎层 ChoiceLogprobs 转换为 proto ChoiceLogprobs。"""
    if not lp:
        return None
    proto_lp = llm_infer_pb2.ChoiceLogprobs()
    for item in lp.content:
        proto_item = llm_infer_pb2.TokenLogprob(
            token=item.token,
            logprob=item.logprob,
        )
        if item.bytes:
            proto_item.bytes.extend(item.bytes)
        for tlp in item.top_logprobs:
            proto_top = llm_infer_pb2.TopLogprob(
                token=tlp.token, logprob=tlp.logprob,
            )
            if tlp.bytes:
                proto_top.bytes.extend(tlp.bytes)
            proto_item.top_logprobs.append(proto_top)
        proto_lp.content.append(proto_item)
    return proto_lp


def _engine_usage_to_proto(usage: UsageStats) -> llm_infer_pb2.Usage:
    """将引擎层 UsageStats 转换为 proto Usage（含 completion_tokens_details）。"""
    proto_usage = llm_infer_pb2.Usage(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    )
    if usage.completion_tokens_details:
        proto_usage.completion_tokens_details.CopyFrom(
            llm_infer_pb2.CompletionTokensDetails(
                reasoning_tokens=usage.completion_tokens_details.reasoning_tokens,
            )
        )
    return proto_usage


# ─────────────────────────────────────────────────
# gRPC Servicer
# ─────────────────────────────────────────────────

class LLMInferServicer(llm_infer_pb2_grpc.LLMInferServiceServicer):
    """gRPC 服务实现 — 多模型路由 + OpenAI Chat Completions API 语义。

    持有 ServiceManager 引用，根据 request.model 字段
    通过 get_or_load_engine() 获取对应的引擎实例。
    """

    def __init__(self, service_manager: ServiceManager):
        self._manager = service_manager

    def _resolve_engine(self, model_name: str, context) -> LLMEngine | None:
        """根据 model_name 获取引擎，失败时设置 gRPC 错误码并返回 None。"""
        try:
            return self._manager.get_or_load_engine(model_name)
        except ValueError as exc:
            # 模型未注册
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(str(exc))
            return None
        except RuntimeError as exc:
            # 加载失败（内存不足等）
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            context.set_details(str(exc))
            return None

    def Health(self, request, context):
        """健康检查 — 返回最近使用的模型状态。"""
        running = self._manager.get_running_service()
        if running:
            return llm_infer_pb2.HealthResponse(
                ready=True,
                model_name=running.model_name,
                message="ok",
            )
        return llm_infer_pb2.HealthResponse(
            ready=False,
            model_name="",
            message="no_model_loaded",
        )

    def ChatCompletion(self, request, context):
        """非流式 Chat Completions — 按 request.model 路由到对应引擎。"""
        request_id = request.request_id or f"chatcmpl-{uuid.uuid4().hex[:12]}"
        model_name = request.model
        logger.info(
            "ChatCompletion request_id=%s model=%s messages=%d n=%d max_tokens=%d",
            request_id, model_name, len(request.messages), request.n, request.max_tokens,
        )

        if not request.messages:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("messages is required and must not be empty")
            return llm_infer_pb2.ChatCompletionResponse()

        if not model_name:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("model is required for multi-model routing")
            return llm_infer_pb2.ChatCompletionResponse()

        engine = self._resolve_engine(model_name, context)
        if engine is None:
            return llm_infer_pb2.ChatCompletionResponse()

        t0 = time.time()
        try:
            engine_request = _proto_request_to_engine(request)
            engine_result = engine.chat_complete(engine_request)
        except Exception as e:
            logger.error("ChatCompletion failed request_id=%s error=%s", request_id, e, exc_info=True)
            _record_stats(
                request_id=request_id, source="local",
                model_name=model_name,
                duration_ms=int((time.time() - t0) * 1000), success=False,
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return llm_infer_pb2.ChatCompletionResponse()

        duration_ms = int((time.time() - t0) * 1000)

        # 构建 proto 响应
        proto_choices = []
        for c in engine_result.choices:
            proto_choice = llm_infer_pb2.Choice(
                index=c.index,
                finish_reason=c.finish_reason,
            )
            if c.message:
                proto_choice.message.CopyFrom(_engine_message_to_proto(c.message))
            lp = _engine_logprobs_to_proto(c.logprobs)
            if lp:
                proto_choice.logprobs.CopyFrom(lp)
            proto_choices.append(proto_choice)

        response = llm_infer_pb2.ChatCompletionResponse(
            id=request_id,
            object="chat.completion",
            created=int(time.time()),
            model=model_name,
            usage=_engine_usage_to_proto(engine_result.usage),
        )
        response.choices.extend(proto_choices)

        # Record stats with enhanced metrics
        reasoning_tokens = (
            engine_result.usage.completion_tokens_details.reasoning_tokens
            if engine_result.usage.completion_tokens_details else 0
        )
        tc_m = engine_result.tool_call_metrics
        im = getattr(engine_result, 'infer_metrics', None)
        _record_stats(
            request_id=request_id, source="local",
            model_name=model_name,
            prompt_tokens=engine_result.usage.prompt_tokens,
            completion_tokens=engine_result.usage.completion_tokens,
            total_tokens=engine_result.usage.total_tokens,
            reasoning_tokens=reasoning_tokens,
            duration_ms=duration_ms, stream=False, success=True,
            tool_call_count=tc_m.tool_call_count if tc_m else 0,
            tool_call_success=tc_m.tool_call_success if tc_m else True,
            tool_call_retried=tc_m.tool_call_retried if tc_m else False,
            tool_call_parse_ms=tc_m.tool_call_parse_ms if tc_m else 0,
        )

        logger.info(
            "ChatCompletion done request_id=%s choices=%d prompt_tokens=%d "
            "completion_tokens=%d duration=%dms lock_wait_ms=%d "
            "prefill_ms=%d decode_ms=%d prefill_tok_s=%.1f decode_tok_s=%.1f",
            request_id, len(proto_choices),
            engine_result.usage.prompt_tokens, engine_result.usage.completion_tokens,
            duration_ms,
            im.lock_wait_ms if im else 0,
            im.prefill_ms if im else 0,
            im.decode_ms if im else 0,
            im.prefill_tok_s if im else 0.0,
            im.decode_tok_s if im else 0.0,
        )
        return response

    def ChatCompletionStream(self, request, context):
        """服务端流式 Chat Completions — 按 request.model 路由到对应引擎。"""
        request_id = request.request_id or f"chatcmpl-{uuid.uuid4().hex[:12]}"
        model_name = request.model
        logger.info(
            "ChatCompletionStream request_id=%s model=%s messages=%d",
            request_id, model_name, len(request.messages),
        )

        if not request.messages:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("messages is required and must not be empty")
            return

        if not model_name:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("model is required for multi-model routing")
            return

        engine = self._resolve_engine(model_name, context)
        if engine is None:
            return

        t0 = time.time()
        try:
            engine_request = _proto_request_to_engine(request)
            stream = engine.stream_chat_complete(engine_request)
        except Exception as e:
            logger.error("ChatCompletionStream failed request_id=%s error=%s", request_id, e, exc_info=True)
            _record_stats(
                request_id=request_id, source="local",
                model_name=model_name,
                duration_ms=int((time.time() - t0) * 1000), stream=True, success=False,
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return

        created = int(time.time())
        model = model_name
        last_usage = None
        last_tool_call_metrics = None
        last_infer_metrics = None  # Track InferMetrics from final chunk

        for chunk_result in stream:
            # Track tool_call_metrics and infer_metrics from final chunk
            if hasattr(chunk_result, 'tool_call_metrics') and chunk_result.tool_call_metrics is not None:
                last_tool_call_metrics = chunk_result.tool_call_metrics
            if hasattr(chunk_result, 'infer_metrics') and chunk_result.infer_metrics is not None:
                last_infer_metrics = chunk_result.infer_metrics
            if chunk_result.usage:
                last_usage = chunk_result.usage

            proto_chunk_choices = []
            for sc in chunk_result.choices:
                proto_delta = llm_infer_pb2.ChatMessageDelta()
                if sc.delta:
                    if sc.delta.role is not None:
                        proto_delta.role = sc.delta.role
                    if sc.delta.content is not None:
                        proto_delta.content = sc.delta.content
                    if sc.delta.reasoning_content is not None:
                        proto_delta.reasoning_content = sc.delta.reasoning_content
                    if sc.delta.tool_calls:
                        for tc in sc.delta.tool_calls:
                            proto_delta.tool_calls.append(
                                llm_infer_pb2.ToolCall(
                                    id=tc.id,
                                    type=tc.type,
                                    function=llm_infer_pb2.FunctionCallDetail(
                                        name=tc.function_name,
                                        arguments=tc.function_arguments,
                                    ),
                                )
                            )

                proto_cc = llm_infer_pb2.ChunkChoice(
                    index=sc.index,
                    delta=proto_delta,
                )
                if sc.finish_reason is not None:
                    proto_cc.finish_reason = sc.finish_reason
                lp = _engine_logprobs_to_proto(sc.logprobs)
                if lp:
                    proto_cc.logprobs.CopyFrom(lp)
                proto_chunk_choices.append(proto_cc)

            proto_chunk = llm_infer_pb2.ChatCompletionChunk(
                id=request_id,
                object="chat.completion.chunk",
                created=created,
                model=model,
            )
            proto_chunk.choices.extend(proto_chunk_choices)

            # 最后一个 chunk 携带 usage（含 completion_tokens_details）
            if chunk_result.usage:
                proto_chunk.usage.CopyFrom(_engine_usage_to_proto(chunk_result.usage))

            yield proto_chunk

        # 记录流式请求统计
        duration_ms = int((time.time() - t0) * 1000)
        reasoning_tokens = 0
        tc_m = last_tool_call_metrics
        if last_usage:
            if last_usage.completion_tokens_details:
                reasoning_tokens = last_usage.completion_tokens_details.reasoning_tokens
            _record_stats(
                request_id=request_id, source="local", model_name=model,
                prompt_tokens=last_usage.prompt_tokens,
                completion_tokens=last_usage.completion_tokens,
                total_tokens=last_usage.total_tokens,
                reasoning_tokens=reasoning_tokens,
                duration_ms=duration_ms, stream=True, success=True,
                tool_call_count=tc_m.tool_call_count if tc_m else 0,
                tool_call_success=tc_m.tool_call_success if tc_m else True,
                tool_call_retried=tc_m.tool_call_retried if tc_m else False,
                tool_call_parse_ms=tc_m.tool_call_parse_ms if tc_m else 0,
            )
        else:
            _record_stats(
                request_id=request_id, source="local", model_name=model,
                duration_ms=duration_ms, stream=True, success=True,
                tool_call_count=tc_m.tool_call_count if tc_m else 0,
                tool_call_success=tc_m.tool_call_success if tc_m else True,
                tool_call_retried=tc_m.tool_call_retried if tc_m else False,
                tool_call_parse_ms=tc_m.tool_call_parse_ms if tc_m else 0,
            )

        logger.info(
            "ChatCompletionStream done request_id=%s duration=%dms "
            "lock_wait_ms=%d prefill_ms=%d decode_ms=%d "
            "prefill_tok_s=%.1f decode_tok_s=%.1f",
            request_id, duration_ms,
            last_infer_metrics.lock_wait_ms if last_infer_metrics else 0,
            last_infer_metrics.prefill_ms if last_infer_metrics else 0,
            last_infer_metrics.decode_ms if last_infer_metrics else 0,
            last_infer_metrics.prefill_tok_s if last_infer_metrics else 0.0,
            last_infer_metrics.decode_tok_s if last_infer_metrics else 0.0,
        )


# ─────────────────────────────────────────────────
# 服务启动入口
# ─────────────────────────────────────────────────

def start_grpc_server(
    service_manager: ServiceManager,
    host: str,
    port: int,
    max_workers: int = 8,
) -> grpc.Server:
    """启动共享 gRPC 推理服务（多模型路由）。

    所有模型共用一个 gRPC server，LLMInferServicer 通过
    ServiceManager.get_or_load_engine() 按 model 路由。
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    llm_infer_pb2_grpc.add_LLMInferServiceServicer_to_server(
        LLMInferServicer(service_manager), server,
    )
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    logger.info("gRPC ChatCompletion server started at %s:%d (multi-model routing)", host, port)
    return server
