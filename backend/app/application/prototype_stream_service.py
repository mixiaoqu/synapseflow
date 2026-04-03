"""Application service for prototype SSE streaming orchestration."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator

from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from app.agents.runtime import AgentEventType, build_graph, get_graph_definition
from app.agents.states.prototype import DocToPrototypeState, prototype_state
from app.application.agent_service import BaseAgentService
from app.application.stream_events import emit_complete, emit_error, emit_event, emit_start
from app.application.workflow_meta import get_node_label, get_node_model
from app.utils.document_parse import parse_uploaded_document


class PrototypeStreamService(BaseAgentService):
    """Streams prototype generation progress as SSE messages."""

    def __init__(self, graph: Any | None = None):
        self._graph_definition = get_graph_definition("doc_to_prototype")
        self._graph = graph or build_graph("doc_to_prototype")

    @staticmethod
    def _progress_after_node(pipeline_ids: tuple[str, ...], node_id: str) -> dict[str, Any]:
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

    @staticmethod
    def _summary_logs(node_id: str, node_state: dict[str, Any]) -> list[dict[str, Any]]:
        logs: list[dict[str, Any]] = []

        if node_id == "prepare_requirement_chunks" and node_state.get("requirements_chunks"):
            logs.append(
                {
                    "level": "success",
                    "content": "Prepared %s requirement chunks"
                    % len(node_state["requirements_chunks"]),
                }
            )
        elif node_id == "chunk_understanding" and node_state.get("chunk_summaries"):
            logs.append(
                {
                    "level": "success",
                    "content": "Generated %s chunk summaries"
                    % len(node_state["chunk_summaries"]),
                }
            )
        elif node_id == "structure_extraction" and node_state.get("structured_spec"):
            spec = node_state["structured_spec"] or {}
            logs.append(
                {
                    "level": "success",
                    "content": "Extracted %s features and %s flows"
                    % (
                        len(spec.get("features") or []),
                        len(spec.get("business_flows") or []),
                    ),
                }
            )
        elif node_id == "normalize_spec" and node_state.get("normalized_spec"):
            normalized = node_state["normalized_spec"] or {}
            logs.append(
                {
                    "level": "success",
                    "content": "Normalized %s features and %s aliases"
                    % (
                        len(normalized.get("features") or []),
                        len(normalized.get("aliases") or []),
                    ),
                }
            )
        elif node_id == "product_design" and node_state.get("site_map"):
            site_map = node_state["site_map"]
            mode = node_state.get("generation_mode", "single")
            titles = ", ".join(
                page.get("title", "") for page in site_map[:5] if page.get("title")
            )
            logs.append(
                {
                    "level": "success",
                    "content": "Planned %s pages in %s mode%s"
                    % (
                        len(site_map),
                        mode,
                        f": {titles}" if titles else "",
                    ),
                }
            )
        elif node_id == "interaction_design" and node_state.get("extracted_requirements"):
            interactions = (node_state["extracted_requirements"] or {}).get("interactions", [])
            logs.append(
                {
                    "level": "success",
                    "content": "Prepared %s interaction definitions" % len(interactions),
                }
            )
        elif node_id == "generate_prototype_from_spec" and node_state.get("generated_html"):
            html_code = node_state["generated_html"]
            logs.append(
                {
                    "level": "success",
                    "content": "Generated %s lines of HTML" % len(html_code.splitlines()),
                }
            )
            if node_state.get("preview_url"):
                logs.append(
                    {
                        "level": "success",
                        "content": "Preview ready at %s" % node_state["preview_url"],
                    }
                )

        return logs

    def build_initial_state(
        self,
        requirements_doc: str,
        *,
        source_filename: str | None = None,
    ) -> DocToPrototypeState:
        """Build the initial state for prototype generation."""

        context = self.build_context(
            request_id=source_filename,
            metadata={"workflow": "doc_to_prototype", "source_filename": source_filename},
        )
        return self.build_state(context, prototype_state(requirements_doc))

    async def event_generator(
        self,
        initial_state: DocToPrototypeState,
    ) -> AsyncGenerator[str, None]:
        """Yield standardized prototype events."""

        run_id = initial_state.get("run_id")
        stream_start = time.time()
        pipeline_ids = self._graph_definition.node_ids
        last_node_state: dict[str, Any] = {}

        def pipeline_order_key(node_id: str) -> int:
            try:
                return pipeline_ids.index(node_id)
            except ValueError:
                return 999

        try:
            total_steps = len(pipeline_ids)
            yield emit_start(run_id, "Starting prototype generation")
            yield emit_event(
                AgentEventType.PROGRESS,
                {"step": 0, "total_steps": total_steps, "percent": 0},
                run_id=run_id,
            )

            if pipeline_ids:
                first_id = pipeline_ids[0]
                first_name = get_node_label("doc_to_prototype", first_id)
                yield emit_event(
                    AgentEventType.NODE_START,
                    {"message": "Starting node"},
                    node_id=first_id,
                    node_name=first_name,
                    run_id=run_id,
                )
                yield emit_event(
                    AgentEventType.LOG,
                    {
                        "level": "info",
                        "content": "Running with model: %s"
                        % (get_node_model("doc_to_prototype", first_id) or "Unknown"),
                    },
                    node_id=first_id,
                    node_name=first_name,
                    run_id=run_id,
                )

            step_wall_start = time.time()
            async for chunk in self._graph.astream(initial_state):
                ordered_ids = sorted(chunk.keys(), key=pipeline_order_key)

                for node_id in ordered_ids:
                    node_state = chunk[node_id]
                    node_name = get_node_label("doc_to_prototype", node_id)
                    last_node_state = node_state

                    for log_entry in self._summary_logs(node_id, node_state):
                        yield emit_event(
                            AgentEventType.LOG,
                            log_entry,
                            node_id=node_id,
                            node_name=node_name,
                            run_id=run_id,
                        )

                    duration = time.time() - step_wall_start
                    yield emit_event(
                        AgentEventType.NODE_COMPLETE,
                        {"duration": round(duration, 2)},
                        node_id=node_id,
                        node_name=node_name,
                        run_id=run_id,
                    )
                    yield emit_event(
                        AgentEventType.LOG,
                        {
                            "level": "success",
                            "content": "Completed in %.2fs" % duration,
                        },
                        node_id=node_id,
                        node_name=node_name,
                        run_id=run_id,
                    )

                    if node_id in pipeline_ids:
                        yield emit_event(
                            AgentEventType.PROGRESS,
                            self._progress_after_node(pipeline_ids, node_id),
                            node_id=node_id,
                            node_name=node_name,
                            run_id=run_id,
                        )

                    try:
                        next_index = pipeline_ids.index(node_id) + 1
                        next_id = pipeline_ids[next_index]
                    except (ValueError, IndexError):
                        next_id = None

                    if next_id:
                        next_name = get_node_label("doc_to_prototype", next_id)
                        yield emit_event(
                            AgentEventType.NODE_START,
                            {"message": "Starting node"},
                            node_id=next_id,
                            node_name=next_name,
                            run_id=run_id,
                        )
                        yield emit_event(
                            AgentEventType.LOG,
                            {
                                "level": "info",
                                "content": "Running with model: %s"
                                % (get_node_model("doc_to_prototype", next_id) or "Unknown"),
                            },
                            node_id=next_id,
                            node_name=next_name,
                            run_id=run_id,
                        )

                    step_wall_start = time.time()

            total_duration = round(time.time() - stream_start, 2)
            raw_preview_url = last_node_state.get("preview_url", "")
            full_preview_url = (
                f"http://localhost:8000{raw_preview_url}" if raw_preview_url else ""
            )
            logger.info(
                "[PrototypeStream] completed in %.1fs preview=%s",
                total_duration,
                raw_preview_url or "(none)",
            )

            yield emit_complete(
                run_id,
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
            yield emit_event(
                AgentEventType.LOG,
                {"level": "success", "content": "Prototype pipeline completed"},
                node_id="system",
                node_name="System",
                run_id=run_id,
            )
        except Exception as exc:
            logger.exception("[PrototypeStream] generation failed: %s", exc)
            yield emit_error(run_id, str(exc))
            yield emit_event(
                AgentEventType.LOG,
                {"level": "error", "content": f"Generation failed: {exc}"},
                node_id="system",
                node_name="System",
                run_id=run_id,
            )

    async def stream_file(self, file: UploadFile) -> StreamingResponse:
        """Parse an uploaded file and return prototype SSE output."""

        content = await file.read()
        text, err = parse_uploaded_document(file.filename or "unknown", content)
        if err:
            raise HTTPException(status_code=400, detail=err)

        initial_state = self.build_initial_state(
            text,
            source_filename=file.filename or "unknown",
        )
        if not initial_state["requirements_doc"]:
            raise HTTPException(status_code=400, detail="Uploaded document is empty")

        async def sse_generator() -> AsyncGenerator[str, None]:
            async for envelope in self.event_generator(initial_state):
                yield envelope
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
