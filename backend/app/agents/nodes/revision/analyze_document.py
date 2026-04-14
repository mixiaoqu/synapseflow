"""Document analysis node for revision workflow."""

from typing import Any, Dict

from loguru import logger

from app.agents.common.document_analysis import (
    build_markdown_section_tree,
    parse_markdown_headings,
)
from app.agents.nodes.revision.chunk_utils import (
    CHUNK_CHAR_LIMIT,
    compute_chunk_positions,
    split_document_into_chunks,
)
from app.agents.states.revision_state import UserDrivenRevisionState


async def analyze_document_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """Parse document structure and compute chunk metadata."""

    doc = (state.get("current_doc") or "").strip()
    if not doc:
        logger.info("[Revision] analyze_document completed with empty document")
        return {
            "doc_structure": [],
            "chunks_meta": [],
            "chunks_positions": [],
        }

    headings = parse_markdown_headings(doc)
    doc_structure = build_markdown_section_tree(headings, document_length=len(doc))
    chunks_meta = split_document_into_chunks(doc, max_chars=CHUNK_CHAR_LIMIT)
    chunks_positions = compute_chunk_positions(doc, chunks_meta)

    logger.info(
        "[Revision] analyze_document headings={} chunks={} length={}",
        len(headings),
        len(chunks_meta),
        len(doc),
    )

    return {
        "doc_structure": doc_structure,
        "chunks_meta": chunks_meta,
        "chunks_positions": chunks_positions,
    }
