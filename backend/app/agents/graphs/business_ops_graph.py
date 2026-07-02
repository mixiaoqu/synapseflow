"""Subgraph for controlled business data operations."""

from __future__ import annotations

import re
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.application.business_operations import (
    PRODUCT_SEARCH_OPERATION_ID,
    BusinessOperationRegistry,
    BusinessOperationService,
)
from app.application.business_operations.schemas import (
    BusinessOperationActor,
    BusinessOperationRequest,
)
from app.agents.states import BusinessOpsState


_PRODUCT_SEARCH_HINTS = (
    "查",
    "查询",
    "搜索",
    "找",
    "商品",
    "库存",
    "价格",
    "售价",
    "条码",
    "sku",
    "SKU",
)


def _compact_text(value: Any, *, limit: int = 120) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit].strip()


def _extract_product_keyword(query: str) -> str:
    keyword = _compact_text(query)
    replacements = [
        "帮我",
        "请帮我",
        "帮忙",
        "查询一下",
        "查一下",
        "查询",
        "搜索",
        "找一下",
        "找",
        "这个门店",
        "这个店",
        "门店",
        "店里",
        "有没有",
        "商品",
        "库存",
        "价格",
        "售价",
        "多少",
        "一下",
    ]
    for text in replacements:
        keyword = keyword.replace(text, " ")
    keyword = re.sub(r"[，。！？、,.!?]", " ", keyword)
    return _compact_text(keyword)


def _format_product_search_answer(result: dict[str, Any]) -> str:
    if not result.get("success"):
        missing_fields = list(result.get("missing_fields") or [])
        if missing_fields:
            labels = "、".join(str(item.get("label") or item.get("key")) for item in missing_fields)
            return f"还需要补充：{labels}。"
        error = result.get("error") or {}
        return str(error.get("message") or result.get("message") or "业务操作执行失败。")

    data = dict(result.get("data") or {})
    items = list(data.get("items") or [])
    if not items:
        return str(result.get("message") or "没有找到相关商品。")

    lines = [str(result.get("message") or "已找到相关商品。")]
    for index, item in enumerate(items, start=1):
        name = item.get("name") or item.get("sku_id") or "未命名商品"
        price = item.get("price")
        stock = item.get("stock")
        unit = item.get("unit") or "件"
        lines.append(f"{index}. {name}，售价 {price} 元，库存 {stock} {unit}")
    return "\n".join(lines)


def _looks_like_product_search(query: str) -> bool:
    normalized = str(query or "").strip()
    return bool(normalized) and any(hint in normalized for hint in _PRODUCT_SEARCH_HINTS)


def _product_count(result: dict[str, Any]) -> int:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    total = data.get("total")
    if isinstance(total, int):
        return total
    items = data.get("items")
    return len(items) if isinstance(items, list) else 0


def create_business_ops_graph():
    """Create the business operations workflow graph."""

    workflow = StateGraph(BusinessOpsState)
    registry = BusinessOperationRegistry()
    service = BusinessOperationService(registry=registry)

    async def _analyze_request_node(state: BusinessOpsState) -> dict[str, Any]:
        stream_writer = get_optional_stream_writer()
        query = str(state.get("query") or "").strip()
        keyword = _extract_product_keyword(query)
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="analyze_request",
            stage="analyze",
            message="正在理解业务数据需求",
            display_stage="understand",
            display_title="🤔 思考您的问题",
            activity_text="正在识别需要查询或操作的业务数据",
        )
        result = {
            "business_request": {
                "raw_query": query,
                "operation_hint": "product.search" if _looks_like_product_search(query) else "",
                "keyword": keyword,
            }
        }
        log_node_info(
            workflow_id="business_ops",
            node_id="analyze_request",
            node_name="分析请求",
            details={
                "原始问题": query,
                "商品关键词": keyword,
            },
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="analyze_request",
            stage="analyze",
            message="已理解业务数据需求",
            display_stage="understand",
            display_title="🤔 思考您的问题",
            activity_text=f"已识别业务数据关键词“{keyword or query}”",
            activity_status="completed",
        )
        return result

    async def _match_operation_node(state: BusinessOpsState) -> dict[str, Any]:
        stream_writer = get_optional_stream_writer()
        operation = registry.get(PRODUCT_SEARCH_OPERATION_ID)
        operation_payload = operation.model_dump() if operation is not None else {}
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="match_operation",
            stage="match",
            message="正在选择业务数据操作",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text="正在准备商品库存和价格查询",
        )
        result = {
            "business_operation": {
                "operation_id": PRODUCT_SEARCH_OPERATION_ID,
                "operation": operation_payload,
            }
        }
        log_node_info(
            workflow_id="business_ops",
            node_id="match_operation",
            node_name="匹配操作",
            details={
                "操作ID": PRODUCT_SEARCH_OPERATION_ID,
                "操作名称": operation_payload.get("name"),
            },
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="match_operation",
            stage="match",
            message="已选择业务数据操作",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text="已准备商品库存和价格查询",
            activity_status="completed",
        )
        return result

    async def _execute_operation_node(state: BusinessOpsState) -> dict[str, Any]:
        stream_writer = get_optional_stream_writer()
        request_info = dict(state.get("business_request") or {})
        keyword = str(request_info.get("keyword") or "").strip()
        store_id = str(state.get("store_id") or "").strip()
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="execute_operation",
            stage="execute",
            message="正在查询业务数据",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text=f"正在查询门店 {store_id or '当前门店'} 的“{keyword}”",
            store_id=store_id or None,
            keyword=keyword,
        )
        result = await service.execute(
            BusinessOperationRequest(
                operation_id=PRODUCT_SEARCH_OPERATION_ID,
                actor=BusinessOperationActor(
                    user_id=state.get("user_id"),
                    external_user_id=state.get("external_user_id"),
                    external_user_name=state.get("external_user_name"),
                ),
                scope={"store_id": state.get("store_id")},
                params={"keyword": keyword},
            )
        )
        result_payload = result.model_dump()
        log_node_info(
            workflow_id="business_ops",
            node_id="execute_operation",
            node_name="执行业务操作",
            details={
                "操作ID": PRODUCT_SEARCH_OPERATION_ID,
                "是否成功": result.success,
                "消息": result.message,
                "结果数": (result.data or {}).get("total"),
            },
        )
        count = _product_count(result_payload)
        activity_text = (
            f"已找到 {count} 个相关商品"
            if result.success
            else str(result.message or "业务查询未完成")
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="execute_operation",
            stage="execute",
            message="业务数据查询完成" if result.success else "业务数据查询未完成",
            display_stage="execute",
            display_title="📊 查询业务数据",
            activity_text=activity_text,
            activity_status="completed" if result.success else "error",
            store_id=store_id or None,
            keyword=keyword,
            result_count=count,
        )
        return {
            "business_operation_result": result_payload,
            "business_result": result_payload.get("data") or {},
        }

    async def _compose_result_node(state: BusinessOpsState) -> dict[str, Any]:
        stream_writer = get_optional_stream_writer()
        operation_result = dict(state.get("business_operation_result") or {})
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="compose_result",
            stage="compose",
            message="正在整理业务结果",
            display_stage="compose",
            display_title="💡 总结最终结果",
            activity_text="正在整理库存和价格信息",
        )
        answer = _format_product_search_answer(operation_result)
        answer_status = "answered" if operation_result.get("success") else "business_operation_failed"
        log_node_info(
            workflow_id="business_ops",
            node_id="compose_result",
            node_name="整理结果",
            details={
                "回答状态": answer_status,
                "回答长度": len(answer),
            },
        )
        emit_activity(
            stream_writer,
            workflow_id="business_ops",
            node_id="compose_result",
            stage="compose",
            message="业务结果整理完成",
            display_stage="compose",
            display_title="💡 总结最终结果",
            activity_text="已整理好库存和价格回复",
            activity_status="completed",
        )
        return {
            "answer": answer,
            "answer_status": answer_status,
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
