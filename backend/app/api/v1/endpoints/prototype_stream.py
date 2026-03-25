"""
原型生成流式 API（SSE）

传输层：每条帧固定为 event: message，业务语义在 JSON 信封的 type 字段。
信封：{ type, node_id, node_name, timestamp, data }
"""
import json
import time
import asyncio
from typing import AsyncGenerator, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from loguru import logger

from app.agents.graphs import (
    create_doc_to_prototype_graph,
    get_doc_to_prototype_pipeline_node_ids,
)
from app.agents.states.prototype import DocToPrototypeState, prototype_state
from app.utils.document_parse import parse_uploaded_document

router = APIRouter()

SSE_EVENT_NAME = "message"


def _stream_envelope(
    typ: str,
    data: Dict[str, Any],
    *,
    node_id: str = "",
    node_name: str = "",
) -> Dict[str, Any]:
    return {
        "type": typ,
        "node_id": node_id,
        "node_name": node_name,
        "timestamp": time.time(),
        "data": data,
    }


def _progress_after_node(
    pipeline_ids: tuple[str, ...],
    node_id: str,
) -> Dict[str, Any]:
    """进度 = 已完成节点数 / 总节点数（当前 node 刚完成，计为已计入）。"""
    total = len(pipeline_ids)
    try:
        completed = pipeline_ids.index(node_id) + 1
    except ValueError:
        completed = 0
    percent = min(100, int(round(100 * completed / total))) if total else 0
    return {
        "step": completed,
        "total_steps": total,
        "percent": percent,
    }


async def prototype_event_generator(
    initial_state: DocToPrototypeState,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    生成流式 JSON 信封序列（由 sse_generator 再封装为 SSE）。

    信封 type：start | progress | log | complete | error
    log 的级别在 data.level：info | success | error
    """
    stream_start = time.time()
    node_names = {
        "prepare_requirement_chunks": "需求分块",
        "chunk_understanding": "分块业务理解",
        "structure_extraction": "结构抽取",
        "normalize_spec": "规格归一",
        "product_design": "产品设计",
        "interaction_design": "交互设计",
        "generate_prototype_from_spec": "原型生成",
    }
    node_models = {
        "prepare_requirement_chunks": "本地切分",
        "chunk_understanding": "Qwen3.5-Plus-分析",
        "structure_extraction": "Qwen3.5-Plus-分析",
        "normalize_spec": "Qwen3.5-Plus-分析",
        "product_design": "Qwen3.5-Plus-规划",
        "interaction_design": "Qwen3.5-Plus-规划",
        "generate_prototype_from_spec": "Qwen3.5-Plus-生成",
    }
    last_node_state: Dict[str, Any] = {}

    try:
        graph = create_doc_to_prototype_graph()
        pipeline_ids = get_doc_to_prototype_pipeline_node_ids(graph)
        total_steps = len(pipeline_ids)

        def _pipeline_order_key(nid: str) -> int:
            try:
                return pipeline_ids.index(nid)
            except ValueError:
                return 999

        yield _stream_envelope(
            "start",
            {"message": "开始生成原型"},
            node_id="system",
            node_name="System",
        )
        yield _stream_envelope(
            "progress",
            {"step": 0, "total_steps": total_steps, "percent": 0},
        )

        # astream 每条 chunk 在节点已跑完后才到达：开始时间取「上一节点结束」或流程起点
        first_id = pipeline_ids[0]
        yield _stream_envelope(
            "log",
            {
                "level": "info",
                "content": "开始执行 (模型: %s)" % node_models.get(first_id, "Unknown"),
            },
            node_id=first_id,
            node_name=node_names.get(first_id, first_id),
        )
        step_wall_start = time.time()

        async for chunk in graph.astream(initial_state):
            ordered_ids = sorted(chunk.keys(), key=_pipeline_order_key)
            for node_id in ordered_ids:
                node_state = chunk[node_id]
                node_name = node_names.get(node_id, node_id)
                last_node_state = node_state

                if node_id == "prepare_requirement_chunks" and node_state.get(
                    "requirements_chunks"
                ):
                    rc = node_state["requirements_chunks"]
                    yield _stream_envelope(
                        "log",
                        {"level": "success", "content": "已切分 %s 个章节块" % len(rc)},
                        node_id=node_id,
                        node_name=node_name,
                    )

                if node_id == "chunk_understanding" and node_state.get("chunk_summaries"):
                    cs = node_state["chunk_summaries"]
                    yield _stream_envelope(
                        "log",
                        {
                            "level": "success",
                            "content": "📚 分块语义: %s 条摘要" % len(cs),
                        },
                        node_id=node_id,
                        node_name=node_name,
                    )

                if node_id == "structure_extraction" and node_state.get("structured_spec"):
                    sp = node_state["structured_spec"] or {}
                    yield _stream_envelope(
                        "log",
                        {
                            "level": "success",
                            "content": "🏗 结构: %s 个功能, %s 条流程"
                            % (
                                len(sp.get("features") or []),
                                len(sp.get("business_flows") or []),
                            ),
                        },
                        node_id=node_id,
                        node_name=node_name,
                    )

                if node_id == "normalize_spec" and node_state.get("normalized_spec"):
                    ns = node_state["normalized_spec"] or {}
                    yield _stream_envelope(
                        "log",
                        {
                            "level": "success",
                            "content": "✨ 归一后 %s 个功能, %s 个别名组"
                            % (
                                len(ns.get("features") or []),
                                len(ns.get("aliases") or []),
                            ),
                        },
                        node_id=node_id,
                        node_name=node_name,
                    )

                if node_id == "product_design" and node_state.get("site_map"):
                    sm = node_state["site_map"]
                    mode = node_state.get("generation_mode", "single")
                    titles = ", ".join(
                        [p.get("title", "") for p in sm[:5] if p.get("title")]
                    )
                    yield _stream_envelope(
                        "log",
                        {
                            "level": "success",
                            "content": "🗺 站点地图: %s 页 (%s) — %s"
                            % (len(sm), mode, titles),
                        },
                        node_id=node_id,
                        node_name=node_name,
                    )

                if node_id == "interaction_design" and node_state.get(
                    "extracted_requirements"
                ):
                    req_data = node_state["extracted_requirements"]
                    interactions = req_data.get("interactions", [])
                    yield _stream_envelope(
                        "log",
                        {
                            "level": "success",
                            "content": "⚡ 交互行为: %s 个" % len(interactions),
                        },
                        node_id=node_id,
                        node_name=node_name,
                    )

                if node_id == "generate_prototype_from_spec" and node_state.get(
                    "generated_html"
                ):
                    html_code = node_state["generated_html"]
                    html_lines = len(html_code.split("\n"))
                    yield _stream_envelope(
                        "log",
                        {
                            "level": "success",
                            "content": "📝 单次生成 %s 行 HTML" % html_lines,
                        },
                        node_id=node_id,
                        node_name=node_name,
                    )
                    if node_state.get("preview_url"):
                        yield _stream_envelope(
                            "log",
                            {
                                "level": "success",
                                "content": "✅ 预览: %s" % node_state.get("preview_url"),
                            },
                            node_id=node_id,
                            node_name=node_name,
                        )

                duration = time.time() - step_wall_start
                yield _stream_envelope(
                    "log",
                    {"level": "success", "content": "执行完成 (耗时: %.2fs)" % duration},
                    node_id=node_id,
                    node_name=node_name,
                )
                if node_id in pipeline_ids:
                    yield _stream_envelope(
                        "progress",
                        _progress_after_node(pipeline_ids, node_id),
                        node_id=node_id,
                        node_name=node_name,
                    )

                try:
                    idx = pipeline_ids.index(node_id)
                    next_id = (
                        pipeline_ids[idx + 1] if idx + 1 < len(pipeline_ids) else None
                    )
                except ValueError:
                    next_id = None

                if next_id:
                    yield _stream_envelope(
                        "log",
                        {
                            "level": "info",
                            "content": "开始执行 (模型: %s)"
                            % node_models.get(next_id, "Unknown"),
                        },
                        node_id=next_id,
                        node_name=node_names.get(next_id, next_id),
                    )
                step_wall_start = time.time()

        total_duration = round(time.time() - stream_start, 2)
        raw_preview_url = last_node_state.get("preview_url", "")
        full_preview_url = (
            "http://localhost:8000%s" % raw_preview_url if raw_preview_url else ""
        )
        logger.info(
            "[原型流式] 流程完成，总耗时 %.1fs，预览 %s",
            total_duration,
            raw_preview_url or "(无)",
        )

        yield _stream_envelope(
            "complete",
            {
                "preview_url": full_preview_url,
                "html": last_node_state.get("generated_html", ""),
                "css": "",
                "js": "",
                "is_valid": last_node_state.get("is_valid", False),
                "validation_errors": last_node_state.get("validation_errors", []),
                "total_duration": total_duration,
                "total_steps": total_steps,
                "product_spec": last_node_state.get("product_spec") or {},
                "normalized_spec": last_node_state.get("normalized_spec") or {},
                "interaction_spec": last_node_state.get("interaction_spec") or {},
            },
        )

        yield _stream_envelope(
            "log",
            {"level": "success", "content": "🎉 原型流程完成"},
            node_id="system",
            node_name="System",
        )

    except Exception as e:
        logger.exception("[原型流式] 生成失败: %s", e)
        yield _stream_envelope(
            "error",
            {"message": str(e)},
            node_id="system",
            node_name="System",
        )
        yield _stream_envelope(
            "log",
            {"level": "error", "content": "生成失败: %s" % str(e)},
            node_id="system",
            node_name="System",
        )


@router.post("/generate/stream/file")
async def generate_prototype_from_file(
    file: UploadFile = File(..., description="需求文档文件"),
):
    """
    通过上传文件流式生成原型（SSE）
    支持格式：.txt, .md, .pdf, .docx，最大 10MB
    """
    content = await file.read()
    text, err = parse_uploaded_document(file.filename or "unknown", content)
    if err:
        raise HTTPException(status_code=400, detail=err)
    initial_state = prototype_state(text)
    if not initial_state["requirements_doc"]:
        raise HTTPException(status_code=400, detail="文件内容为空")

    async def sse_generator():
        async for envelope in prototype_event_generator(initial_state):
            sse_message = (
                "event: %s\ndata: %s\n\n"
                % (SSE_EVENT_NAME, json.dumps(envelope, ensure_ascii=False))
            )
            yield sse_message
            await asyncio.sleep(0)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
