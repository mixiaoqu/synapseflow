"""Translate Agent runtime chunks into transport-neutral event data."""

from __future__ import annotations

from typing import Any


class AgentStreamAdapter:
    """Validate LangGraph stream chunks before the SSE layer renders them."""

    @staticmethod
    def execution_identity(data: dict[str, Any]) -> dict[str, Any]:
        identity: dict[str, Any] = {}
        call_id = data.get("tool_call_id")
        if isinstance(call_id, str) and call_id:
            identity["tool_call_id"] = call_id
        round_number = data.get("round")
        if isinstance(round_number, int) and round_number > 0:
            identity["round"] = round_number
        return identity

    @staticmethod
    def parse_chunk(chunk: Any) -> tuple[str | None, dict[str, Any]]:
        if isinstance(chunk, tuple) and len(chunk) == 2:
            mode, data = chunk
            if isinstance(mode, str) and isinstance(data, dict):
                return mode, data
            return None, {}
        if not isinstance(chunk, dict):
            return None, {}
        chunk_type = str(chunk.get("type") or "").strip()
        data = chunk.get("data")
        if chunk_type in {"updates", "custom"} and isinstance(data, dict):
            return chunk_type, data
        return None, {}

    @staticmethod
    def complete_payload(
        *,
        response: dict[str, Any],
        assistant_id: int | None,
        assistant_name: str | None,
        session_id: str | None,
        log_id: int | None,
    ) -> dict[str, Any]:
        """Map the clean graph response to the current Widget wire contract."""

        answer = str(response.get("answer") or "")
        status = str(response.get("status") or "failed")
        sources = list(response.get("sources") or [])
        return {
            "answer": answer,
            "answer_text": answer,
            "answer_status": status,
            "backend_citations": sources,
            "retrieved_docs": sources,
            "assistant_id": assistant_id,
            "assistant_name": assistant_name,
            "session_id": session_id,
            "log_id": log_id,
        }
