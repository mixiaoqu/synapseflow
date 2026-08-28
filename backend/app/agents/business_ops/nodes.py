"""Node implementations for the business operations workflow."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from loguru import logger

from app.agents.business_ops.decision import (
    analyze_business_request,
    build_combined_business_result,
    replan_business_params,
    serialize_tool_candidates,
    summarize_unavailable_reasons,
)
from app.agents.business_ops.result import build_business_task_result
from app.agents.business_ops.state import BusinessOpsState
from app.agents.business_ops.tools.execution import build_tool_step
from app.agents.common.execution_budget import ExecutionBudgetExceededError, consume_operation
from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.application.business_operations import BusinessOperationService
from app.application.business_operations.schemas import (
    BusinessOperationActor,
    BusinessOperationRequest,
)


def build_business_ops_nodes(
    *,
    service: BusinessOperationService,
    planner_factory: Callable[[], Any] | None,
) -> dict[str, Callable[..., Any]]:
    async def _analyze_request_node(state: BusinessOpsState) -> dict[str, Any]:
        started_at = perf_counter()
        stream_writer = get_optional_stream_writer()
        query = str(state.get("query") or "").strip()
        call_history = list(state.get("business_call_history") or [])
        availability_snapshot = await service.get_tool_availability_snapshot(
            state.get("project_app_id")
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="analyze_request",
            stage="analyze",
            message="正在理解业务数据需求",
            display_stage="understand",
            display_title="🤔 思考您的问题",
            activity_text="识别可用的业务工具和调用参数",
        )
        operations = await service.list_available_operations(state.get("project_app_id"))
        candidates = [
            item
            for item in serialize_tool_candidates(operations)
            if item.get("read_only") is True
        ]
        if not candidates:
            reason_summary = summarize_unavailable_reasons(
                dict(availability_snapshot.get("unavailable_reason_counts") or {})
            )
            if availability_snapshot.get("tool_grant_count"):
                reason_text = (
                    f"当前应用端已授权 {availability_snapshot.get('tool_grant_count')} 个工具，"
                    f"但没有可直接执行的工具。{reason_summary}"
                    if reason_summary
                    else "当前应用端已授权工具，但没有已发布的可执行工具。"
                )
            else:
                reason_text = "当前应用端没有授权任何业务工具。"
            request_info = {
                "raw_query": query,
                "status": "unsupported",
                "operation_id": None,
                "params": {},
                "clarification": None,
                "reason": reason_text,
            }
        else:
            try:
                request_info = await analyze_business_request(
                    query,
                    candidates=candidates,
                    dependency_results=dict(state.get("dependency_results") or {}),
                    call_history=call_history,
                    runtime_context=dict(state.get("runtime_context") or {}),
                    task_context=str(state.get("task_context") or ""),
                    llm_factory=planner_factory,
                )
            except Exception:
                logger.exception("[business_ops] failed to plan dynamic tool call. query={}", query)
                request_info = {
                    "raw_query": query,
                    "status": "planner_failed",
                    "operation_id": None,
                    "params": {},
                    "clarification": None,
                    "reason": "业务工具调用计划生成失败。",
                }
        operation_name = next(
            (item["name"] for item in candidates if item["id"] == request_info.get("operation_id")),
            None,
        )
        log_node_info(
            workflow_id="business_ops",
            node_id="analyze_request",
            node_name="分析请求",
            details={
                "应用ID": state.get("project_app_id"),
                "授权工具数": availability_snapshot.get("tool_grant_count"),
                "候选工具数": len(candidates),
                "可用工具Key": list(availability_snapshot.get("available_tool_keys") or []),
                "不可用原因": dict(availability_snapshot.get("unavailable_reason_counts") or {}),
                "选择工具": request_info.get("operation_id"),
                "计划状态": request_info.get("status"),
                "规划参数": dict(request_info.get("params") or {}),
                "已调用次数": len(call_history),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="analyze_request",
            stage="analyze",
            message="业务需求分析完成",
            display_stage="understand",
            display_title="🤔 思考您的问题",
            activity_text=(
                f"已选择“{operation_name}”"
                if operation_name
                else (
                    "业务数据已足够"
                    if request_info.get("status") == "complete"
                    else "未找到可直接执行的业务工具"
                )
            ),
            activity_status="completed",
        )
        result = {
            "available_business_tools": candidates,
            "business_request": request_info,
            "business_retry_count": 0,
            "business_retry_error": {},
            "business_call_count": len(call_history),
            "business_call_history": call_history,
        }
        if request_info.get("status") != "ready":
            success = request_info.get("status") == "complete" and bool(call_history)
            message = (
                "业务数据查询已完成。"
                if success
                else str(
                    request_info.get("clarification")
                    or request_info.get("reason")
                    or "业务查询未完成。"
                )
            )
            result["business_operation_result"] = {
                "success": success,
                "operation_id": call_history[-1].get("tool_id") if call_history else "",
                "message": message,
                "data": build_combined_business_result(call_history),
                "error": (
                    None
                    if success
                    else {
                        "code": str(request_info.get("status") or "UNSUPPORTED").upper(),
                        "message": message,
                        "retryable": request_info.get("status") == "clarification_required",
                    }
                ),
            }
            result["business_result"] = build_combined_business_result(call_history)
        return result

    async def _match_operation_node(state: BusinessOpsState) -> dict[str, Any]:
        started_at = perf_counter()
        stream_writer = get_optional_stream_writer()
        request_info = dict(state.get("business_request") or {})
        operation_id = str(request_info.get("operation_id") or "")
        candidates = list(state.get("available_business_tools") or [])
        operation = next((item for item in candidates if item.get("id") == operation_id), None)
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="match_operation",
            stage="match",
            message="正在确认业务工具",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text="校验工具能力和参数",
        )
        log_node_info(
            workflow_id="business_ops",
            node_id="match_operation",
            node_name="匹配操作",
            details={"操作ID": operation_id or None, "操作名称": (operation or {}).get("name")},
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="match_operation",
            stage="match",
            message="业务工具确认完成",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text=(
                f"已准备调用“{operation['name']}”" if operation else "没有可执行的工具调用"
            ),
            activity_status="completed",
        )
        return {
            "business_operation": {
                "operation_id": operation_id or None,
                "operation": operation or {},
            }
        }

    async def _execute_operation_node(state: BusinessOpsState) -> dict[str, Any]:
        started_at = perf_counter()
        stream_writer = get_optional_stream_writer()
        request_info = dict(state.get("business_request") or {})
        operation_info = dict(state.get("business_operation") or {})
        operation = dict(operation_info.get("operation") or {})
        status = str(request_info.get("status") or "unsupported")
        if status != "ready" or not operation:
            message = (
                str(request_info.get("clarification") or "").strip()
                or str(request_info.get("reason") or "").strip()
                or "当前问题还不能转换为确定的业务工具调用。"
            )
            result_payload = {
                "success": False,
                "operation_id": request_info.get("operation_id") or "",
                "message": message,
                "data": {},
                "error": {
                    "code": status.upper(),
                    "message": message,
                    "retryable": status == "clarification_required",
                },
            }
            return {"business_operation_result": result_payload, "business_result": {}}

        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="execute_operation",
            stage="execute",
            message="正在调用业务工具",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text=f"调用“{operation.get('name') or operation.get('id')}”",
        )
        scope = {
            **dict(state.get("trusted_scope") or {}),
            "project_app_id": state.get("project_app_id"),
            "product_id": state.get("product_id"),
            "project_id": state.get("project_id"),
            "store_id": state.get("store_id"),
        }
        try:
            consume_operation()
        except ExecutionBudgetExceededError:
            message = "本次执行预算已用尽，已取得的业务结果予以保留。"
            return {
                "business_request": {**request_info, "status": "limit_reached", "reason": message},
                "business_operation_result": {
                    "success": False,
                    "operation_id": operation["id"],
                    "message": message,
                    "error": {
                        "code": "EXECUTION_BUDGET_EXHAUSTED",
                        "message": message,
                        "retryable": False,
                    },
                },
                "business_result": build_combined_business_result(
                    list(state.get("business_call_history") or [])
                ),
            }
        result = await service.execute(
            BusinessOperationRequest(
                operation_id=str(operation["id"]),
                project_app_id=state.get("project_app_id"),
                session_id=state.get("session_id"),
                actor=BusinessOperationActor(
                    user_id=state.get("user_id"),
                    external_user_id=state.get("external_user_id"),
                    external_user_name=state.get("external_user_name"),
                ),
                scope={key: value for key, value in scope.items() if value is not None},
                params=dict(request_info.get("params") or {}),
            )
        )
        retry_count = int(state.get("business_retry_count") or 0)
        error_code = result.error.code if result.error else ""
        if retry_count >= 1 and error_code in {"INVALID_PARAMS", "MCP_INVALID_PARAMS"}:
            result.message = "业务查询参数自动修正后仍未通过校验。"
            if result.error is not None:
                result.error.message = result.message
                result.error.retryable = False
        result_payload = result.model_dump()
        call_history = list(state.get("business_call_history") or [])
        should_retry = (
            not result.success
            and retry_count < 1
            and error_code in {"INVALID_PARAMS", "MCP_INVALID_PARAMS"}
        )
        if not should_retry:
            step = build_tool_step(
                index=len(call_history) + 1,
                tool_id=operation["id"],
                arguments=dict(request_info.get("params") or {}),
                result=result,
            ).model_dump()
            step["call_id"] = f"call_{step['index']}"
            step["tool_name"] = operation.get("name") or operation["id"]
            call_history.append(step)
        log_node_info(
            workflow_id="business_ops",
            node_id="execute_operation",
            node_name="执行业务操作",
            details={
                "操作ID": operation["id"],
                "是否成功": bool(result_payload.get("success")),
                "HTTP状态": result.http_status,
                "工具调用耗时毫秒": result.duration_ms,
                "规划参数": dict(request_info.get("params") or {}),
                "缺少参数": [field.key for field in result.missing_fields],
                "错误代码": (result_payload.get("error") or {}).get("code"),
                "错误信息": (result_payload.get("error") or {}).get("message"),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="execute_operation",
            stage="execute",
            message="业务工具调用完成" if result_payload.get("success") else "业务工具调用未完成",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text=(
                "已获取业务数据" if result_payload.get("success") else result_payload.get("message")
            ),
            activity_status="completed" if result_payload.get("success") else "error",
            tool_key=operation["id"],
            duration_ms=result.duration_ms,
        )
        return {
            "business_operation_result": result_payload,
            "business_result": build_combined_business_result(call_history),
            "business_call_count": len(call_history),
            "business_call_history": call_history,
        }

    async def _replan_operation_params_node(state: BusinessOpsState) -> dict[str, Any]:
        started_at = perf_counter()
        stream_writer = get_optional_stream_writer()
        request_info = dict(state.get("business_request") or {})
        operation = dict((state.get("business_operation") or {}).get("operation") or {})
        result_payload = dict(state.get("business_operation_result") or {})
        error = dict(result_payload.get("error") or {})
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="replan_operation_params",
            stage="execute",
            message="正在修正业务查询参数",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text="根据工具参数约束重新整理查询条件",
        )
        try:
            replanned = await replan_business_params(
                query=str(state.get("query") or ""),
                operation=operation,
                previous_params=dict(request_info.get("params") or {}),
                error=error,
                runtime_context=dict(state.get("runtime_context") or {}),
                llm_factory=planner_factory,
            )
            action = str(replanned.get("action") or "fail")
            next_request = {
                **request_info,
                "status": {
                    "retry": "ready",
                    "clarify": "clarification_required",
                    "fail": "repair_failed",
                }[action],
                "params": replanned["params"],
                "clarification": replanned.get("clarification_question"),
                "reason": replanned["reason"] or "已完成参数修正判断。",
            }
        except Exception:
            logger.exception(
                "[business_ops] failed to replan tool params. operation={}",
                operation.get("id"),
            )
            next_request = {
                **request_info,
                "status": "repair_failed",
                "clarification": None,
                "reason": "业务查询参数自动修正失败。",
            }
        log_node_info(
            workflow_id="business_ops",
            node_id="replan_operation_params",
            node_name="修正业务参数",
            details={
                "操作ID": operation.get("id"),
                "原参数": dict(request_info.get("params") or {}),
                "修正参数": dict(next_request.get("params") or {}),
                "错误代码": error.get("code"),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="replan_operation_params",
            stage="execute",
            message="业务查询参数修正完成",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text="已重新整理查询条件",
            activity_status="completed",
        )
        return {
            "business_request": next_request,
            "business_retry_count": int(state.get("business_retry_count") or 0) + 1,
            "business_retry_error": error,
        }

    def _route_after_analyze(state: BusinessOpsState) -> str:
        return (
            "execute"
            if (state.get("business_request") or {}).get("status") == "ready"
            else "compose"
        )

    def _route_after_execute(state: BusinessOpsState) -> str:
        result_payload = dict(state.get("business_operation_result") or {})
        error = dict(result_payload.get("error") or {})
        if (
            not result_payload.get("success")
            and int(state.get("business_retry_count") or 0) < 1
            and str(error.get("code") or "") in {"INVALID_PARAMS", "MCP_INVALID_PARAMS"}
        ):
            return "replan"
        if result_payload.get("success"):
            return "analyze"
        return "compose"

    def _route_after_replan(state: BusinessOpsState) -> str:
        return (
            "execute"
            if (state.get("business_request") or {}).get("status") == "ready"
            else "compose"
        )

    async def _compose_result_node(state: BusinessOpsState) -> dict[str, Any]:
        started_at = perf_counter()
        stream_writer = get_optional_stream_writer()
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="compose_result",
            stage="compose",
            message="正在整理业务结果",
            display_stage="compose",
            display_title="💡 总结最终结果",
            activity_text="整理可用于回答的业务数据",
        )
        task_result = build_business_task_result(state)
        log_node_info(
            workflow_id="business_ops",
            node_id="compose_result",
            node_name="整理结果",
            details={
                "结果状态": task_result.get("status"),
                "回答状态": task_result.get("answer_status"),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="compose_result",
            stage="compose",
            message="业务结果整理完成",
            display_stage="compose",
            display_title="💡 总结最终结果",
            activity_text="已整理好业务数据",
            activity_status="completed",
        )
        return {
            "task_result": task_result,
            "answer_status": task_result.get("answer_status"),
            "retrieved_docs": [],
            "backend_citations": [],
        }

    return {
        "analyze_request": _analyze_request_node,
        "match_operation": _match_operation_node,
        "execute_operation": _execute_operation_node,
        "replan_operation_params": _replan_operation_params_node,
        "compose_result": _compose_result_node,
        "route_after_analyze": _route_after_analyze,
        "route_after_execute": _route_after_execute,
        "route_after_replan": _route_after_replan,
    }
