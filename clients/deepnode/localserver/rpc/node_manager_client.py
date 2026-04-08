"""与 platform nodemanager 的 gRPC 双向流长连接客户端。

功能：
- 推理服务启动后建立与 nodemanager 的常驻长连接
- 首条消息完成鉴权注册
- 定时心跳保活
- 接收并执行推理任务，通过 ServiceManager 按 model 路由到对应引擎
- 断线自动指数退避重连
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import TYPE_CHECKING

import grpc

from generated import node_tunnel_pb2, node_tunnel_pb2_grpc, llm_infer_pb2

if TYPE_CHECKING:
    from service.manager import ServiceManager

logger = logging.getLogger(__name__)


def _record_stats(**kwargs) -> None:
    """延迟导入 statistics 模块并记录推理请求，避免循环导入。"""
    from service.statistics import InferRecord, get_statistics_db
    get_statistics_db().record(InferRecord(**kwargs))

# 重连退避参数
_INITIAL_BACKOFF_SEC = 2
_MAX_BACKOFF_SEC = 60
_BACKOFF_MULTIPLIER = 2


class NodeManagerClient:
    """与 nodemanager 的长连接客户端。

    通过 ServiceManager 按 task.request.model 路由到对应引擎，
    支持多模型推理任务分发。

    Args:
        grpc_target: nodemanager gRPC 地址
        simei: 设备唯一标识
        auth_token: 鉴权令牌
        model_name: 注册时上报的默认模型名称
        engine_type: 推理引擎类型（用于注册上报）
        service_manager: 多模型服务管理器
        use_tls: 是否使用 TLS 加密连接
        ca_cert: CA 证书文件路径（PEM），留空使用系统根证书
    """

    def __init__(
        self,
        grpc_target: str,
        simei: str,
        auth_token: str,
        model_name: str,
        engine_type: str,
        service_manager: ServiceManager | None = None,
        use_tls: bool = False,
        ca_cert: str = "",
    ):
        self._target = grpc_target
        self._simei = simei
        self._token = auth_token
        self._model_name = model_name
        self._engine_type = engine_type
        self._service_manager = service_manager
        self._use_tls = use_tls
        self._ca_cert = ca_cert

        self._channel: grpc.Channel | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._heartbeat_interval = 10
        self._session_id = ""
        self._outgoing: _MessageQueue | None = None  # 当前连接的消息队列（用于重载后上报模型列表）

    def set_service_manager(self, manager: ServiceManager) -> None:
        """设置服务管理器，用于按 model 路由推理任务。"""
        self._service_manager = manager

    def start(self) -> None:
        """启动长连接（后台线程，支持自动重连）。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._connect_loop,
            name="nodemanager-tunnel",
            daemon=True,
        )
        self._thread.start()
        logger.info("nodemanager tunnel client started target=%s simei=%s", self._target, self._simei)

    def stop(self) -> None:
        """停止长连接。"""
        self._running = False
        if self._channel:
            self._channel.close()
            self._channel = None
        logger.info("nodemanager tunnel client stopped simei=%s", self._simei)

    def _connect_loop(self) -> None:
        """带指数退避的重连循环。"""
        backoff = _INITIAL_BACKOFF_SEC
        while self._running:
            try:
                self._run_tunnel()
                # 正常退出（服务端关闭），重置退避
                backoff = _INITIAL_BACKOFF_SEC
            except Exception as exc:
                logger.warning(
                    "nodemanager tunnel disconnected simei=%s err=%s, reconnecting in %ds",
                    self._simei, exc, backoff,
                )
            if not self._running:
                break
            time.sleep(backoff)
            backoff = min(backoff * _BACKOFF_MULTIPLIER, _MAX_BACKOFF_SEC)

    def _run_tunnel(self) -> None:
        """执行一次完整的隧道连接生命周期。"""
        # 根据 TLS 配置创建 gRPC channel
        if self._use_tls:
            root_certs = None
            if self._ca_cert:
                with open(self._ca_cert, "rb") as f:
                    root_certs = f.read()
            credentials = grpc.ssl_channel_credentials(root_certificates=root_certs)
            self._channel = grpc.secure_channel(self._target, credentials)
            logger.info("nodemanager tunnel: TLS channel created target=%s", self._target)
        else:
            self._channel = grpc.insecure_channel(self._target)
        stub = node_tunnel_pb2_grpc.NodeTunnelServiceStub(self._channel)

        # 创建双向流通道
        # 使用生成器发送消息，接收线程在主循环中处理
        outgoing = _MessageQueue()
        self._outgoing = outgoing
        stream = stub.Tunnel(outgoing)

        try:
            # ── 注册 ──
            # 构建模型名称列表：从 ServiceManager 获取所有已注册模型
            model_names = self._get_all_model_names()
            outgoing.send(node_tunnel_pb2.ClientMessage(
                register=node_tunnel_pb2.RegisterRequest(
                    simei=self._simei,
                    auth_token=self._token,
                    model_name=self._model_name,  # 兼容旧版 NodeManager
                    engine=self._engine_type,
                    model_names=model_names,       # 多模型列表
                ),
            ))

            # 等待注册响应
            resp = next(stream)
            ack = resp.register_ack
            if not ack or not ack.success:
                msg = ack.message if ack else "no register ack"
                raise RuntimeError(f"register failed: {msg}")

            self._session_id = ack.session_id
            self._heartbeat_interval = ack.heartbeat_interval_sec or 10
            logger.info(
                "nodemanager tunnel connected session=%s heartbeat=%ds",
                self._session_id, self._heartbeat_interval,
            )

            # ── 启动心跳线程 ──
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                args=(outgoing,),
                name="tunnel-heartbeat",
                daemon=True,
            )
            heartbeat_thread.start()

            # ── 事件循环：接收服务端消息 ──
            for server_msg in stream:
                if not self._running:
                    break
                self._handle_server_message(server_msg, outgoing)

        finally:
            self._outgoing = None
            outgoing.close()
            if self._channel:
                self._channel.close()
                self._channel = None

    def _heartbeat_loop(self, outgoing: _MessageQueue) -> None:
        """定时发送心跳。"""
        while self._running and not outgoing.closed:
            try:
                outgoing.send(node_tunnel_pb2.ClientMessage(
                    heartbeat=node_tunnel_pb2.Heartbeat(
                        timestamp_ms=int(time.time() * 1000),
                    ),
                ))
            except Exception:
                break
            time.sleep(self._heartbeat_interval)

    def _handle_server_message(
        self,
        msg: node_tunnel_pb2.ServerMessage,
        outgoing: _MessageQueue,
    ) -> None:
        """路由处理服务端消息。"""
        payload = msg.WhichOneof("payload")

        if payload == "heartbeat":
            # 服务端心跳回复，无需额外处理
            return

        if payload == "inference_task":
            task = msg.inference_task
            logger.info(
                "tunnel: received task task_id=%s stream=%s model=%s",
                task.task_id, task.stream, task.request.model,
            )
            # 在独立线程执行推理，避免阻塞事件循环
            threading.Thread(
                target=self._execute_task,
                args=(task, outgoing),
                name=f"task-{task.task_id}",
                daemon=True,
            ).start()
            return

        if payload == "task_cancel":
            cancel = msg.task_cancel
            logger.info("tunnel: task cancelled task_id=%s reason=%s", cancel.task_id, cancel.reason)
            # TODO: 通知引擎取消正在执行的任务
            return

        if payload == "reload_models":
            cmd = msg.reload_models
            logger.info("tunnel: received reload_models command reason=%s", cmd.reason)
            # 在独立线程执行模型重载，避免阻塞事件循环
            threading.Thread(
                target=self._handle_reload_models,
                args=(cmd.reason,),
                name="reload-models",
                daemon=True,
            ).start()
            return

        logger.warning("tunnel: unknown server message type=%s", payload)

    def _handle_reload_models(self, reason: str) -> None:
        """处理模型重载指令：重新拉取平台分配的模型配置并同步到 ServiceManager。

        流程：
          1. 创建临时 PlatformClient 连接 manager
          2. 调用 get_multi_model_deploy_configs 获取最新模型分配列表
          3. 调用 ServiceManager.sync_models 同步注册表（新增/更新/移除）
          4. 关闭临时 gRPC channel

        任何环节失败仅记录日志，不影响已有推理服务的运行。
        """
        from config import get_config
        from rpc.platform_client import PlatformClient

        logger.info("reload_models: starting reload reason=%s simei=%s", reason, self._simei)

        platform_client = None
        try:
            cfg = get_config()
            platform_client = PlatformClient(
                grpc_target=cfg.platform.manager_grpc_target,
                auth_token=self._token,
                **cfg.platform.tls_kwargs,
            )

            # 重新拉取平台分配的模型配置列表
            deploy_configs = platform_client.get_multi_model_deploy_configs(
                simei=self._simei,
                supported_models=[],
            )

            if not deploy_configs:
                logger.warning("reload_models: platform returned empty config list, skipping sync")
                return

            # 同步模型注册表（新增/更新 + 移除不再分配的旧模型）
            if self._service_manager is not None:
                self._service_manager.sync_models(deploy_configs)
                logger.info(
                    "reload_models: sync complete, %d models in new config",
                    len(deploy_configs),
                )
                # 通过隧道通知 NodeManager 新的模型列表，更新路由表
                self._notify_model_update()
            else:
                logger.warning("reload_models: service_manager not available, skipping sync")

        except Exception as exc:
            logger.error("reload_models: failed reason=%s err=%s", reason, exc, exc_info=True)
        finally:
            if platform_client is not None:
                platform_client.close()

    def _notify_model_update(self) -> None:
        """通过隧道发送 UpdateModelsNotify，告知 NodeManager 当前支持的模型列表。"""
        model_names = self._get_all_model_names()
        if self._outgoing is not None and not self._outgoing.closed:
            try:
                self._outgoing.send(node_tunnel_pb2.ClientMessage(
                    update_models=node_tunnel_pb2.UpdateModelsNotify(
                        model_names=model_names,
                    ),
                ))
                logger.info("reload_models: notified nodemanager with updated models=%s", model_names)
            except Exception as exc:
                logger.warning("reload_models: failed to notify nodemanager: %s", exc)
        else:
            logger.warning("reload_models: outgoing queue not available, skip model update notify")

    def report_error_logs(self, entries: list) -> None:
        """通过隧道流批量发送错误日志到 NodeManager。

        Args:
            entries: ErrorLogEntry proto 消息列表。
        """
        outgoing = self._outgoing
        if outgoing is None or outgoing.closed:
            logger.warning("report_error_logs: outgoing queue not available, dropping %d logs", len(entries))
            return

        try:
            outgoing.send(node_tunnel_pb2.ClientMessage(
                error_log=node_tunnel_pb2.ErrorLogReport(
                    entries=entries,
                ),
            ))
            logger.debug("report_error_logs: sent %d error log entries", len(entries))
        except Exception as exc:
            logger.warning("report_error_logs: failed to send: %s", exc)

    def _get_all_model_names(self) -> list[str]:
        """从 ServiceManager 获取所有已注册的模型名称列表。"""
        if self._service_manager is None:
            return [self._model_name] if self._model_name else []
        models = self._service_manager.list_models()
        names = [m["model_name"] for m in models if m.get("model_name")]
        return names if names else ([self._model_name] if self._model_name else [])

    def _execute_task(
        self,
        task: node_tunnel_pb2.InferenceTask,
        outgoing: _MessageQueue,
    ) -> None:
        """执行推理任务 — 通过 ServiceManager 按 model 获取引擎并回传结果。"""
        task_model = task.request.model or self._model_name

        if self._service_manager is None:
            outgoing.send(node_tunnel_pb2.ClientMessage(
                task_result=node_tunnel_pb2.TaskResult(
                    task_id=task.task_id,
                    success=False,
                    error="service manager not available",
                ),
            ))
            return

        t0 = time.time()
        try:
            engine = self._service_manager.get_or_load_engine(task_model)
        except (ValueError, RuntimeError) as exc:
            logger.error("tunnel: engine not available task_id=%s model=%s err=%s", task.task_id, task_model, exc)
            _record_stats(
                request_id=task.task_id, source="tunnel",
                model_name=task_model,
                duration_ms=int((time.time() - t0) * 1000),
                stream=task.stream, success=False,
            )
            outgoing.send(node_tunnel_pb2.ClientMessage(
                task_result=node_tunnel_pb2.TaskResult(
                    task_id=task.task_id,
                    success=False,
                    error=str(exc),
                ),
            ))
            return

        try:
            engine_request = _proto_to_engine_request(task.request)

            if task.stream:
                self._execute_stream_task(task.task_id, task_model, engine, engine_request, outgoing, t0)
            else:
                self._execute_non_stream_task(task.task_id, task_model, engine, engine_request, outgoing, t0)
        except Exception as exc:
            logger.error("tunnel: task execution failed task_id=%s err=%s", task.task_id, exc, exc_info=True)
            _record_stats(
                request_id=task.task_id, source="tunnel",
                model_name=task_model,
                duration_ms=int((time.time() - t0) * 1000),
                stream=task.stream, success=False,
            )
            outgoing.send(node_tunnel_pb2.ClientMessage(
                task_result=node_tunnel_pb2.TaskResult(
                    task_id=task.task_id,
                    success=False,
                    error=str(exc),
                ),
            ))

    def _execute_non_stream_task(self, task_id: str, model_name: str, engine, engine_request, outgoing: _MessageQueue, t0: float) -> None:
        """执行非流式推理任务。"""
        from rpc.infer_server import (
            _engine_message_to_proto,
            _engine_logprobs_to_proto,
            _engine_usage_to_proto,
        )

        result = engine.chat_complete(engine_request)
        duration_ms = int((time.time() - t0) * 1000)

        # 构建 proto response
        proto_choices = []
        for c in result.choices:
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

        request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        response = llm_infer_pb2.ChatCompletionResponse(
            id=request_id,
            object="chat.completion",
            created=int(time.time()),
            model=model_name,
            usage=_engine_usage_to_proto(result.usage),
        )
        response.choices.extend(proto_choices)

        outgoing.send(node_tunnel_pb2.ClientMessage(
            task_result=node_tunnel_pb2.TaskResult(
                task_id=task_id,
                success=True,
                response=response,
            ),
        ))

        # 记录统计
        reasoning_tokens = (
            result.usage.completion_tokens_details.reasoning_tokens
            if result.usage.completion_tokens_details else 0
        )
        _record_stats(
            request_id=request_id, source="tunnel", model_name=model_name,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
            reasoning_tokens=reasoning_tokens,
            duration_ms=duration_ms, stream=False, success=True,
        )
        logger.info("tunnel: task completed task_id=%s choices=%d duration=%dms", task_id, len(proto_choices), duration_ms)

    def _execute_stream_task(self, task_id: str, model_name: str, engine, engine_request, outgoing: _MessageQueue, t0: float) -> None:
        """执行流式推理任务。"""
        from rpc.infer_server import (
            _engine_logprobs_to_proto,
            _engine_usage_to_proto,
        )

        stream = engine.stream_chat_complete(engine_request)
        created = int(time.time())
        request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        last_usage = None

        for chunk_result in stream:
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
                model=model_name,
            )
            proto_chunk.choices.extend(proto_chunk_choices)

            if chunk_result.usage:
                proto_chunk.usage.CopyFrom(_engine_usage_to_proto(chunk_result.usage))

            # 检查是否为最后一个 chunk（有 finish_reason 的 choice）
            is_done = any(sc.finish_reason is not None for sc in chunk_result.choices)

            outgoing.send(node_tunnel_pb2.ClientMessage(
                task_chunk=node_tunnel_pb2.TaskStreamChunk(
                    task_id=task_id,
                    success=True,
                    chunk=proto_chunk,
                    done=is_done,
                ),
            ))

        # 记录流式请求统计
        duration_ms = int((time.time() - t0) * 1000)
        reasoning_tokens = 0
        if last_usage:
            if last_usage.completion_tokens_details:
                reasoning_tokens = last_usage.completion_tokens_details.reasoning_tokens
            _record_stats(
                request_id=request_id, source="tunnel", model_name=model_name,
                prompt_tokens=last_usage.prompt_tokens,
                completion_tokens=last_usage.completion_tokens,
                total_tokens=last_usage.total_tokens,
                reasoning_tokens=reasoning_tokens,
                duration_ms=duration_ms, stream=True, success=True,
            )
        else:
            _record_stats(
                request_id=request_id, source="tunnel", model_name=model_name,
                duration_ms=duration_ms, stream=True, success=True,
            )

        logger.info("tunnel: stream task completed task_id=%s duration=%dms", task_id, duration_ms)


class _MessageQueue:
    """线程安全的消息发送队列，实现 gRPC 双向流的 request iterator 接口。"""

    def __init__(self):
        self._queue: list[node_tunnel_pb2.ClientMessage] = []
        self._cond = threading.Condition()
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def send(self, msg: node_tunnel_pb2.ClientMessage) -> None:
        """向队列推入一条消息。"""
        with self._cond:
            if self._closed:
                return
            self._queue.append(msg)
            self._cond.notify()

    def close(self) -> None:
        """关闭队列，终止迭代。"""
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def __iter__(self):
        return self

    def __next__(self) -> node_tunnel_pb2.ClientMessage:
        with self._cond:
            while not self._queue and not self._closed:
                self._cond.wait()
            if self._queue:
                return self._queue.pop(0)
            raise StopIteration


def _proto_to_engine_request(proto_req):
    """将 proto ChatCompletionRequest 转换为引擎层请求。
    
    复用 infer_server.py 中已有的转换函数。
    """
    from rpc.infer_server import _proto_request_to_engine
    return _proto_request_to_engine(proto_req)
