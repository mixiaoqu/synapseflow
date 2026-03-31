"""Application service for admin-facing knowledge-base curation."""

import json
from typing import Any, AsyncGenerator, Dict

from app.agents.graphs import create_kb_curation_graph
from app.models.schemas.qa import QARequest, QAResponse


class KbCurationService:
    """Encapsulates admin-facing knowledge-base curation orchestration."""

    def __init__(self, graph: Any | None = None):
        self._graph = graph or create_kb_curation_graph()

    @staticmethod
    def build_initial_state(request: QARequest) -> Dict[str, Any]:
        """Build graph input state from the request payload."""
        return {
            "messages": [],
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
            "collection_id": request.collection_id,
        }

    async def invoke(self, request: QARequest) -> QAResponse:
        """Run the curation graph and map its result to the response schema."""
        result = await self._graph.ainvoke(self.build_initial_state(request))
        return QAResponse(
            answer=result["answer"],
            confidence_score=result["confidence_score"],
            iteration=result["iteration"],
            retrieved_docs=result.get("retrieved_docs", []),
            iteration_history=result.get("iteration_history", []),
            document_issues=result.get("document_issues", []),
            session_id=request.session_id,
        )

    async def stream(self, request: QARequest) -> AsyncGenerator[str, None]:
        """Stream graph chunks as SSE messages."""
        try:
            async for chunk in self._graph.astream(self.build_initial_state(request)):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            error_msg = {"error": str(exc)}
            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"


kb_curation_service = KbCurationService()
