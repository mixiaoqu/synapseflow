"""Application service for admin-facing knowledge-base curation."""

from __future__ import annotations

from typing import Any, AsyncGenerator

from app.agents.runtime import build_graph, get_graph_definition
from app.application.agent_service import BaseAgentService
from app.application.stream_events import (
    emit_complete,
    emit_error,
    emit_node_complete,
    emit_node_start,
    emit_start,
)
from app.application.workflow_meta import get_node_label
from app.models.schemas.qa import QARequest, QAResponse


class KbCurationService(BaseAgentService):
    """Encapsulates admin-facing knowledge-base curation orchestration."""

    def __init__(self, graph: Any | None = None):
        self._graph_definition = get_graph_definition("kb_curation")
        self._graph = graph or build_graph("kb_curation")

    def build_initial_state(
        self,
        request: QARequest,
        *,
        user_id: int,
    ) -> dict[str, Any]:
        """Build graph input state from the request payload."""

        context = self.build_context(
            user_id=user_id,
            knowledge_base_id=request.knowledge_base_id,
            request_id=request.session_id,
            metadata={"workflow": "kb_curation"},
        )
        return self.build_state(
            context,
            {
                "query": request.query,
                "optimized_query": "",
                "retrieved_docs": [],
                "context": "",
                "answer": "",
                "confidence_score": 0.0,
                "iteration": 0,
                "max_iterations": request.max_iterations,
                "should_continue": True,
                "iteration_history": [],
                "last_evaluation_feedback": None,
                "document_issues": [],
            },
        )

    @staticmethod
    def _node_summary(node_id: str, state: dict[str, Any]) -> dict[str, Any]:
        """Build a compact summary for a completed node."""

        if node_id == "query_optimizer":
            return {"optimized_query": state.get("optimized_query", "")}
        if node_id == "retrieve":
            return {
                "retrieved_count": len(state.get("retrieved_docs", [])),
                "kb_retrieval_status": state.get("kb_retrieval_status"),
            }
        if node_id == "answer":
            return {"answer_length": len(state.get("answer", ""))}
        if node_id == "evaluate":
            return {
                "iteration": state.get("iteration", 0),
                "confidence_score": state.get("confidence_score", 0.0),
                "should_continue": state.get("should_continue", False),
            }
        return {"keys": sorted(state.keys())}

    async def invoke(self, request: QARequest, *, user_id: int) -> QAResponse:
        """Run the curation graph and map its result to the response schema."""

        result = await self._graph.ainvoke(self.build_initial_state(request, user_id=user_id))
        return QAResponse(
            answer=result["answer"],
            confidence_score=result["confidence_score"],
            iteration=result["iteration"],
            retrieved_docs=result.get("retrieved_docs", []),
            iteration_history=result.get("iteration_history", []),
            document_issues=result.get("document_issues", []),
            session_id=request.session_id,
        )

    async def stream(
        self,
        request: QARequest,
        *,
        user_id: int,
    ) -> AsyncGenerator[str, None]:
        """Stream graph chunks as standardized SSE events."""

        state = self.build_initial_state(request, user_id=user_id)
        run_id = state.get("run_id")
        final_state = dict(state)
        seen_nodes: set[str] = set()

        try:
            yield emit_start(run_id, "Starting knowledge-base curation")

            async for chunk in self._graph.astream(state):
                ordered_ids = [
                    node_id for node_id in self._graph_definition.node_ids if node_id in chunk
                ]
                for node_id in ordered_ids:
                    node_state = chunk[node_id]
                    node_name = get_node_label("kb_curation", node_id)

                    if node_id not in seen_nodes:
                        yield emit_node_start(
                            node_id,
                            node_name,
                            run_id,
                            message=f"Starting {node_name.lower()}",
                        )
                        seen_nodes.add(node_id)

                    final_state.update(node_state)
                    yield emit_node_complete(
                        node_id,
                        node_name,
                        run_id,
                        self._node_summary(node_id, node_state),
                    )

            yield emit_complete(
                run_id,
                {
                    "answer": final_state.get("answer", ""),
                    "confidence_score": final_state.get("confidence_score", 0.0),
                    "iteration": final_state.get("iteration", 0),
                    "retrieved_docs": final_state.get("retrieved_docs", []),
                    "iteration_history": final_state.get("iteration_history", []),
                    "document_issues": final_state.get("document_issues", []),
                    "session_id": request.session_id,
                },
            )
        except Exception as exc:
            yield emit_error(run_id, str(exc))


kb_curation_service = KbCurationService()
