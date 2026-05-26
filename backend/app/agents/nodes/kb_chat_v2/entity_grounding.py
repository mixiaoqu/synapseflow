"""Entity grounding node for kb_chat_v2."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from loguru import logger

from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatV2State
from app.services.kb_entity_grounding import ground_graph_entities


async def kb_chat_v2_entity_grounding_node(
    state: KbChatV2State,
    *,
    grounding_func: Callable[..., Awaitable[dict[str, Any]]] = ground_graph_entities,
) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    emit_progress(
        stream_writer,
        node_id="entity_grounding",
        stage="grounding",
        message="正在对齐图谱实体",
    )
    candidate_entities = list(state.get("candidate_entities") or [])
    if not state.get("graph_enabled"):
        logger.info(
            "[KB Entity Grounding V2] skipped | graph_enabled=false candidate_entities={}",
            candidate_entities,
        )
        return {
            "grounded_entities": [],
            "ungrounded_entities": [],
            "grounding_trace": {"skipped": True, "input_count": 0, "grounded_count": 0},
        }
    result = await grounding_func(
        candidate_entities=candidate_entities,
        knowledge_base_id=int(state.get("knowledge_base_id") or 0),
        team_id=int(state.get("team_id") or 0),
    )
    logger.info(
        "[KB Entity Grounding V2] done | candidate_entities={} grounded_entities={} ungrounded_entities={} grounding_trace={}",
        candidate_entities,
        result.get("grounded_entities") or [],
        result.get("ungrounded_entities") or [],
        result.get("grounding_trace") or {},
    )
    return result
