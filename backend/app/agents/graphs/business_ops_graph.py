"""Subgraph for dynamically configured business tools."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from langgraph.graph import END, StateGraph
from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.common.sub_agent_result import build_business_sub_agent_result
from app.agents.states import BusinessOpsState
from app.application.business_operations import BusinessOperationService
from app.application.business_operations.schemas import (
    BusinessOperationActor,
    BusinessOperationRequest,
)
from app.core.llm import get_llm_for_planner


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item if isinstance(item, str) else str(item.get("text", ""))
            for item in content
            if isinstance(item, (str, dict))
        )
    return str(content or "")


def _compact_text(value: Any, *, limit: int = 180) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit].strip()


def _serialize_tool_candidates(records) -> list[dict[str, Any]]:
    return [
        {
            "id": record.tool.tool_key,
            "name": record.tool.name,
            "description": record.tool.description or "",
            "typical_queries": list(record.tool.typical_queries or []),
            "risk_level": record.tool.risk_level,
            "requires_confirmation": bool(record.tool.requires_confirmation),
            "params": [
                {
                    "key": item.get("key"),
                    "label": item.get("label"),
                    "type": item.get("type", "text"),
                    "required": bool(item.get("required")),
                    "description": item.get("description", ""),
                }
                for item in list(record.tool.params_schema or [])
                if isinstance(item, dict) and item.get("key")
            ],
        }
        for record in records
    ]


def _build_business_request_analysis_prompt(
    query: str,
    candidates: list[dict[str, Any]],
) -> str:
    tools_json = json.dumps(candidates, ensure_ascii=False, default=str)
    return f"""
你是业务工具调用规划器。根据用户问题，从候选工具中选择一个最匹配的工具并提取参数。

只输出 JSON，不要输出 Markdown、解释或自然语言回答。

规则：
1. operation_id 只能使用候选工具中的 id，不能发明工具。
2. params 只能包含所选工具定义的参数；不要把礼貌用语、疑问词或命令词当成参数值。
3. 缺少必填信息时返回 clarification_required，并给出一个简短中文追问。
4. 没有任何工具能满足请求时返回 unsupported，不要勉强选择。
5. 不要回答业务问题，只生成可执行计划。

输出格式：
{{
  "status": "ready | clarification_required | unsupported",
  "operation_id": "候选工具 id 或 null",
  "params": {{}},
  "clarification": null,
  "reason": "简短选择依据"
}}

候选工具：
{tools_json}

用户问题：
{query.strip()}
""".strip()


def _normalize_business_request(
    parsed: dict[str, Any],
    *,
    query: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_map = {str(item["id"]): item for item in candidates}
    status = str(parsed.get("status") or "unsupported").strip().lower()
    if status not in {"ready", "clarification_required", "unsupported"}:
        status = "unsupported"
    operation_id = str(parsed.get("operation_id") or "").strip()
    if operation_id not in candidate_map:
        operation_id = ""
        if status == "ready":
            status = "unsupported"
    raw_params = parsed.get("params") if isinstance(parsed.get("params"), dict) else {}
    allowed_params = {
        str(item.get("key") or "") for item in candidate_map.get(operation_id, {}).get("params", [])
    }
    params = {
        str(key): value
        for key, value in raw_params.items()
        if str(key) in allowed_params and value is not None
    }
    return {
        "raw_query": query,
        "status": status,
        "operation_id": operation_id or None,
        "params": params,
        "clarification": (
            _compact_text(parsed.get("clarification"), limit=200)
            if parsed.get("clarification")
            else None
        ),
        "reason": _compact_text(parsed.get("reason"), limit=240),
    }


async def _analyze_business_request_with_llm(
    query: str,
    *,
    candidates: list[dict[str, Any]],
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    llm = (
        llm_factory()
        if llm_factory is not None
        else get_llm_for_planner(
            temperature=0,
            max_tokens=700,
        )
    )
    response = await llm.ainvoke(_build_business_request_analysis_prompt(query, candidates))
    content = _coerce_text(getattr(response, "content", response))
    parsed = parse_llm_json_object(content)
    if not parsed:
        raise ValueError("业务工具规划模型未返回有效 JSON")
    return _normalize_business_request(parsed, query=query, candidates=candidates)


def create_business_ops_graph(
    *,
    planner_llm_factory: Callable[[], Any] | None = None,
    answer_llm_factory: Callable[[], Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
):
    """Create the dynamic business operations workflow graph."""

    del answer_llm_factory
    planner_factory = planner_llm_factory or llm_factory
    workflow = StateGraph(BusinessOpsState)
    service = BusinessOperationService()

    async def _analyze_request_node(state: BusinessOpsState) -> dict[str, Any]:
        stream_writer = get_optional_stream_writer()
        query = str(state.get("query") or "").strip()
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
        records = await service.list_available_tools(state.get("project_app_id"))
        candidates = _serialize_tool_candidates(records)
        if not candidates:
            request_info = {
                "raw_query": query,
                "status": "unsupported",
                "operation_id": None,
                "params": {},
                "clarification": None,
                "reason": "当前应用端没有已发布且可用的业务工具。",
            }
        else:
            try:
                request_info = await _analyze_business_request_with_llm(
                    query,
                    candidates=candidates,
                    llm_factory=planner_factory,
                )
            except Exception:
                logger.exception("[business_ops] failed to plan dynamic tool call. query={}", query)
                request_info = {
                    "raw_query": query,
                    "status": "unsupported",
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
                "候选工具数": len(candidates),
                "选择工具": request_info.get("operation_id"),
                "计划状态": request_info.get("status"),
            },
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
                f"已选择“{operation_name}”" if operation_name else "未找到可直接执行的业务工具"
            ),
            activity_status="completed",
        )
        return {
            "available_business_tools": candidates,
            "business_request": request_info,
        }

    async def _match_operation_node(state: BusinessOpsState) -> dict[str, Any]:
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
        page_context = dict(state.get("page_context") or {})
        scope = {
            "project_app_id": state.get("project_app_id"),
            "product_id": state.get("product_id"),
            "project_id": state.get("project_id"),
            "store_id": state.get("store_id"),
            **page_context,
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
        result_payload = result.model_dump()
        log_node_info(
            workflow_id="business_ops",
            node_id="execute_operation",
            node_name="执行业务操作",
            details={
                "操作ID": operation["id"],
                "是否成功": result.success,
                "HTTP状态": result.http_status,
                "耗时毫秒": result.duration_ms,
            },
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="execute_operation",
            stage="execute",
            message="业务工具调用完成" if result.success else "业务工具调用未完成",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text=("已获取业务数据" if result.success else result.message),
            activity_status="completed" if result.success else "error",
            tool_key=operation["id"],
            duration_ms=result.duration_ms,
        )
        return {
            "business_operation_result": result_payload,
            "business_result": result_payload.get("data") or {},
        }

    async def _compose_result_node(state: BusinessOpsState) -> dict[str, Any]:
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
        sub_agent_result = build_business_sub_agent_result(state)
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
            "sub_agent_result": sub_agent_result,
            "answer_status": sub_agent_result.get("answer_status"),
            "retrieved_docs": [],
            "backend_citations": [],
        }

    workflow.add_node("analyze_request", _analyze_request_node)
    workflow.add_node("match_operation", _match_operation_node)
    workflow.add_node("execute_operation", _execute_operation_node)
    workflow.add_node("compose_result", _compose_result_node)
    workflow.set_entry_point("analyze_request")
    workflow.add_edge("analyze_request", "match_operation")
    workflow.add_edge("match_operation", "execute_operation")
    workflow.add_edge("execute_operation", "compose_result")
    workflow.add_edge("compose_result", END)
    return workflow.compile()
