"""Application service for revision orchestration."""

from __future__ import annotations

from typing import Any

from app.agents.runtime import build_graph, get_graph_definition
from app.application.agent_service import BaseAgentService
from app.models.schemas.revision import SuggestRevisionRequest, SuggestRevisionResponse


class RevisionService(BaseAgentService):
    """Encapsulates the revision graph invocation flow."""

    def __init__(self, graph: Any | None = None):
        self._graph_definition = get_graph_definition("suggest_revision")
        self._graph = graph or build_graph("suggest_revision")

    def build_initial_state(self, request: SuggestRevisionRequest) -> dict[str, Any]:
        """Build the initial state for revision requests."""

        context = self.build_context(
            request_id=str(request.doc_id) if request.doc_id is not None else None,
            metadata={"workflow": "suggest_revision", "doc_id": request.doc_id},
        )
        return self.build_state(
            context,
            {
                "original_doc": request.document,
                "current_doc": request.document,
                "user_suggestions": request.suggestions,
                "parsed_tasks": [],
                "doc_structure": [],
                "chunks_meta": [],
                "chunks_positions": [],
                "affected_chunk_indices": [],
                "section_hints": {},
                "revised_document": "",
                "doc_id": request.doc_id,
            },
        )

    async def suggest(self, request: SuggestRevisionRequest) -> SuggestRevisionResponse:
        """Run the revision graph and return the revised document."""

        result = await self._graph.ainvoke(self.build_initial_state(request))
        return SuggestRevisionResponse(
            revised_document=result.get("revised_document", result.get("current_doc", "")),
        )


revision_service = RevisionService()
