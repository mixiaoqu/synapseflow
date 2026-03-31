"""Application service for revision orchestration."""

from typing import Any

from app.agents.graphs import create_suggest_revision_graph
from app.models.schemas.revision import SuggestRevisionRequest, SuggestRevisionResponse


class RevisionService:
    """Encapsulates the revision graph invocation flow."""

    def __init__(self, graph: Any | None = None):
        self._graph = graph or create_suggest_revision_graph()

    @staticmethod
    def build_initial_state(request: SuggestRevisionRequest) -> dict[str, Any]:
        return {
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
        }

    async def suggest(self, request: SuggestRevisionRequest) -> SuggestRevisionResponse:
        result = await self._graph.ainvoke(self.build_initial_state(request))
        return SuggestRevisionResponse(
            revised_document=result.get("revised_document", result.get("current_doc", "")),
        )


revision_service = RevisionService()
