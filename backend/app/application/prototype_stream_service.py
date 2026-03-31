"""Application service for prototype SSE streaming orchestration."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator

from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from app.agents.graphs import (
    create_doc_to_prototype_graph,
    get_doc_to_prototype_pipeline_node_ids,
)
from app.agents.states.prototype import DocToPrototypeState, prototype_state
from app.utils.document_parse import parse_uploaded_document

SSE_EVENT_NAME = "message"


class PrototypeStreamService:
    """Streams prototype generation progress as SSE messages."""

    def __init__(self, graph: Any | None = None):
        self._graph = graph or create_doc_to_prototype_graph()

    @staticmethod
    def _stream_envelope(
        typ: str,
        data: dict[str, Any],
        *,
        node_id: str = "",
        node_name: str = "",
    ) -> dict[str, Any]:
        return {
            "type": typ,
            "node_id": node_id,
            "node_name": node_name,
            "timestamp": time.time(),
            "data": data,
        }

    @staticmethod
    def _progress_after_node(
        pipeline_ids: tuple[str, ...],
        node_id: str,
    ) -> dict[str, Any]:
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

    async def event_generator(
        self,
        initial_state: DocToPrototypeState,
    ) -> AsyncGenerator[dict[str, Any], None]:
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
        last_node_state: dict[str, Any] = {}

        try:
            pipeline_ids = get_doc_to_prototype_pipeline_node_ids(self._graph)
            total_steps = len(pipeline_ids)

            def _pipeline_order_key(nid: str) -> int:
                try:
                    return pipeline_ids.index(nid)
                except ValueError:
                    return 999

            yield self._stream_envelope(
                "start",
                {"message": "开始生成原型"},
                node_id="system",
                node_name="System",
            )
            yield self._stream_envelope(
                "progress",
                {"step": 0, "total_steps": total_steps, "percent": 0},
            )

            first_id = pipeline_ids[0]
            yield self._stream_envelope(
                "log",
                {
                    "level": "info",
                    "content": "开始执行（模型: %s)"
                    % node_models.get(first_id, "Unknown"),
                },
                node_id=first_id,
                node_name=node_names.get(first_id, first_id),
            )
            step_wall_start = time.time()

            async for chunk in self._graph.astream(initial_state):
                ordered_ids = sorted(chunk.keys(), key=_pipeline_order_key)
                for node_id in ordered_ids:
                    node_state = chunk[node_id]
                    node_name = node_names.get(node_id, node_id)
                    last_node_state = node_state

                    if node_id == "prepare_requirement_chunks" and node_state.get(
                        "requirements_chunks"
                    ):
                        rc = node_state["requirements_chunks"]
                        yield self._stream_envelope(
                            "log",
                            {"level": "success", "content": f"已切分 {len(rc)} 个章节块"},
                            node_id=node_id,
                            node_name=node_name,
                        )

                    if node_id == "chunk_understanding" and node_state.get("chunk_summaries"):
                        cs = node_state["chunk_summaries"]
                        yield self._stream_envelope(
                            "log",
                            {"level": "success", "content": f"分块语义: {len(cs)} 条摘要"},
                            node_id=node_id,
                            node_name=node_name,
                        )

                    if node_id == "structure_extraction" and node_state.get("structured_spec"):
                        spec = node_state["structured_spec"] or {}
                        yield self._stream_envelope(
                            "log",
                            {
                                "level": "success",
                                "content": "结构: %s 个功能 / %s 条流程"
                                % (
                                    len(spec.get("features") or []),
                                    len(spec.get("business_flows") or []),
                                ),
                            },
                            node_id=node_id,
                            node_name=node_name,
                        )

                    if node_id == "normalize_spec" and node_state.get("normalized_spec"):
                        normalized = node_state["normalized_spec"] or {}
                        yield self._stream_envelope(
                            "log",
                            {
                                "level": "success",
                                "content": "归一后: %s 个功能 / %s 组别名"
                                % (
                                    len(normalized.get("features") or []),
                                    len(normalized.get("aliases") or []),
                                ),
                            },
                            node_id=node_id,
                            node_name=node_name,
                        )

                    if node_id == "product_design" and node_state.get("site_map"):
                        site_map = node_state["site_map"]
                        mode = node_state.get("generation_mode", "single")
                        titles = ", ".join(
                            [page.get("title", "") for page in site_map[:5] if page.get("title")]
                        )
                        yield self._stream_envelope(
                            "log",
                            {
                                "level": "success",
                                "content": f"站点地图: {len(site_map)} 页 ({mode}) - {titles}",
                            },
                            node_id=node_id,
                            node_name=node_name,
                        )

                    if node_id == "interaction_design" and node_state.get(
                        "extracted_requirements"
                    ):
                        req_data = node_state["extracted_requirements"]
                        interactions = req_data.get("interactions", [])
                        yield self._stream_envelope(
                            "log",
                            {
                                "level": "success",
                                "content": f"交互行为: {len(interactions)} 项",
                            },
                            node_id=node_id,
                            node_name=node_name,
                        )

                    if node_id == "generate_prototype_from_spec" and node_state.get(
                        "generated_html"
                    ):
                        html_code = node_state["generated_html"]
                        html_lines = len(html_code.split("\n"))
                        yield self._stream_envelope(
                            "log",
                            {
                                "level": "success",
                                "content": f"单次生成 {html_lines} 行 HTML",
                            },
                            node_id=node_id,
                            node_name=node_name,
                        )
                        if node_state.get("preview_url"):
                            yield self._stream_envelope(
                                "log",
                                {
                                    "level": "success",
                                    "content": f"预览: {node_state.get('preview_url')}",
                                },
                                node_id=node_id,
                                node_name=node_name,
                            )

                    duration = time.time() - step_wall_start
                    yield self._stream_envelope(
                        "log",
                        {"level": "success", "content": f"执行完成 (耗时: {duration:.2f}s)"},
                        node_id=node_id,
                        node_name=node_name,
                    )
                    if node_id in pipeline_ids:
                        yield self._stream_envelope(
                            "progress",
                            self._progress_after_node(pipeline_ids, node_id),
                            node_id=node_id,
                            node_name=node_name,
                        )

                    try:
                        idx = pipeline_ids.index(node_id)
                        next_id = pipeline_ids[idx + 1] if idx + 1 < len(pipeline_ids) else None
                    except ValueError:
                        next_id = None

                    if next_id:
                        yield self._stream_envelope(
                            "log",
                            {
                                "level": "info",
                                "content": "开始执行（模型: %s)"
                                % node_models.get(next_id, "Unknown"),
                            },
                            node_id=next_id,
                            node_name=node_names.get(next_id, next_id),
                        )
                    step_wall_start = time.time()

            total_duration = round(time.time() - stream_start, 2)
            raw_preview_url = last_node_state.get("preview_url", "")
            full_preview_url = (
                f"http://localhost:8000{raw_preview_url}" if raw_preview_url else ""
            )
            logger.info(
                "[原型流式] 流程完成，总耗时 %.1fs，预览 %s",
                total_duration,
                raw_preview_url or "(无)",
            )

            yield self._stream_envelope(
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

            yield self._stream_envelope(
                "log",
                {"level": "success", "content": "原型流程完成"},
                node_id="system",
                node_name="System",
            )
        except Exception as exc:
            logger.exception("[原型流式] 生成失败: %s", exc)
            yield self._stream_envelope(
                "error",
                {"message": str(exc)},
                node_id="system",
                node_name="System",
            )
            yield self._stream_envelope(
                "log",
                {"level": "error", "content": f"生成失败: {exc}"},
                node_id="system",
                node_name="System",
            )

    async def stream_file(self, file: UploadFile) -> StreamingResponse:
        content = await file.read()
        text, err = parse_uploaded_document(file.filename or "unknown", content)
        if err:
            raise HTTPException(status_code=400, detail=err)

        initial_state = prototype_state(text)
        if not initial_state["requirements_doc"]:
            raise HTTPException(status_code=400, detail="文件内容为空")

        async def sse_generator() -> AsyncGenerator[str, None]:
            async for envelope in self.event_generator(initial_state):
                yield "event: %s\ndata: %s\n\n" % (
                    SSE_EVENT_NAME,
                    json.dumps(envelope, ensure_ascii=False),
                )
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


prototype_stream_service = PrototypeStreamService()
