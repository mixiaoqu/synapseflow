"""Request understanding node for the top-level Agent workflow."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.main.state import AgentState
from app.agents.main.understanding import build_request_understanding


def build_understand_node(*, planner_llm_factory: Callable[[], Any] | None):
    async def understand_node(state: AgentState) -> dict[str, Any]:
        started_at = perf_counter()
        writer = get_optional_stream_writer()
        agent_input = state["input"]
        conversation = agent_input["conversation"]
        emit_activity(
            writer,
            workflow_id="agent",
            node_id="understand",
            stage="understand",
            message="正在理解您的需求",
            display_stage="understand",
            display_title="🤔 思考您的问题",
            activity_text="理解目标和任务结构",
        )
        understanding = await build_request_understanding(
            agent_input["query"],
            chat_history=list(conversation.get("history") or []),
            memory_summary=conversation.get("summary"),
            page_context=dict(agent_input["page_context"]),
            runtime_context=dict(agent_input["runtime_context"]),
            llm_factory=planner_llm_factory,
        )
        result: dict[str, Any] = {"understanding": understanding}
        if (
            understanding["handling"] == "delegated"
            and understanding["clarity"] == "clear"
            and understanding["task_structure"] == "atomic"
        ):
            result["tasks"] = [
                {
                    "task_id": "task_1",
                    "goal": understanding["goal"] or agent_input["query"],
                    "depends_on": [],
                }
            ]
        log_node_info(
            workflow_id="agent",
            node_id="understand",
            node_name="理解请求",
            details={
                "处理方式": understanding.get("handling"),
                "任务结构": understanding.get("task_structure"),
                "目标是否清晰": understanding.get("clarity"),
                "原因": understanding.get("reason"),
            },
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        return result

    return understand_node
