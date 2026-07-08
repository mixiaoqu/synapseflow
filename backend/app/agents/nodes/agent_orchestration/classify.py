"""Classification node for top-level agent orchestration."""

from __future__ import annotations

from typing import Any, Callable

from app.agents.common.agent_intent import build_agent_classification
from app.agents.common.node_logging import log_node_info
from app.agents.common.streaming import emit_activity, get_optional_stream_writer
from app.agents.runtime.sub_agents import SubAgentDefinition
from app.agents.states import AgentState


def build_classify_node(
    *,
    sub_agents: tuple[SubAgentDefinition, ...],
    planner_llm_factory: Callable[[], Any] | None,
):
    async def classify_node(state: AgentState) -> dict[str, Any]:
        writer = get_optional_stream_writer()
        emit_activity(
            writer,
            workflow_id="agent",
            node_id="classify",
            stage="classify",
            message="正在识别请求类型",
            display_stage="classify",
            display_title="识别任务",
            activity_text="判断任务形态和子智能体需求",
        )
        classification = await build_agent_classification(
            str(state.get("normalized_query") or state.get("query") or ""),
            sub_agents=sub_agents,
            chat_history=list(state.get("chat_history") or []),
            memory_summary=state.get("memory_summary"),
            page_context=dict(state.get("page_context") or {}),
            llm_factory=planner_llm_factory,
        )
        log_node_info(
            workflow_id="agent",
            node_id="classify",
            node_name="识别任务",
            details={
                "请求类型": classification.get("request_type"),
                "任务形态": classification.get("task_shape"),
                "目标清晰度": classification.get("goal_clarity"),
                "子智能体提示": classification.get("domain_hints"),
                "风险提示": classification.get("risk_hint"),
                "判断原因": classification.get("reason"),
            },
        )
        emit_activity(
            writer,
            workflow_id="agent",
            node_id="classify",
            stage="classify",
            message="请求类型识别完成",
            display_stage="classify",
            display_title="识别任务",
            activity_text="已明确任务形态",
            activity_status="completed",
        )
        return {"classification": classification}

    return classify_node
