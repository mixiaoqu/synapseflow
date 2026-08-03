"""Task planning for executable routes."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Callable

from app.agents.common.llm_json import parse_llm_json_object
from app.agents.common.node_logging import log_node_info
from app.agents.main.nodes.constants import ROUTE_MULTI_SUB_AGENT
from app.agents.main.nodes.utils import coerce_text
from app.agents.main.state import AgentState
from app.core.llm import get_llm_for_planner


def _validate_steps(
    raw_steps: list[Any],
    *,
    targets: set[str],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    task_ids: set[str] = set()
    for raw in raw_steps[:4]:
        if not isinstance(raw, dict):
            raise ValueError("Plan step must be an object")
        task_id = str(raw.get("task_id") or "").strip()
        sub_agent_id = str(raw.get("sub_agent_id") or "").strip()
        goal = str(raw.get("goal") or "").strip()
        raw_expected_facts = raw.get("expected_facts") or []
        expected_fact_items = (
            [raw_expected_facts]
            if isinstance(raw_expected_facts, str)
            else list(raw_expected_facts)
        )
        expected_facts = list(
            dict.fromkeys(
                str(item).strip()
                for item in expected_fact_items
                if str(item).strip()
            )
        )[:6]
        depends_on = [str(item).strip() for item in list(raw.get("depends_on") or [])]
        if not task_id or task_id in task_ids:
            raise ValueError("Plan contains missing or duplicate task_id")
        if sub_agent_id not in targets or not goal:
            raise ValueError("Plan contains unknown capability or empty goal")
        if task_id in depends_on:
            raise ValueError("Plan task cannot depend on itself")
        task_ids.add(task_id)
        steps.append(
            {
                "task_id": task_id,
                "sub_agent_id": sub_agent_id,
                "goal": goal,
                "expected_facts": expected_facts,
                "depends_on": depends_on,
            }
        )
    if any(dep not in task_ids for step in steps for dep in step["depends_on"]):
        raise ValueError("Plan contains unknown dependency")
    if sum(step["sub_agent_id"] == "knowledge_qa" for step in steps) > 3:
        raise ValueError("Plan contains more than three knowledge goals")
    if not steps:
        raise ValueError("Plan must contain at least one task")
    pending = {step["task_id"]: set(step["depends_on"]) for step in steps}
    resolved: set[str] = set()
    while pending:
        ready = {task_id for task_id, deps in pending.items() if deps <= resolved}
        if not ready:
            raise ValueError("Plan contains cyclic dependencies")
        resolved.update(ready)
        for task_id in ready:
            pending.pop(task_id)
    return steps


async def _plan_multi_agent(
    state: AgentState,
    *,
    planner_llm_factory: Callable[[], Any] | None,
) -> list[dict[str, Any]]:
    routing = state["routing"]
    prompt = f"""
Create the smallest executable task plan. Return JSON only:
{{"steps":[{{"task_id":"goal_1","sub_agent_id":"knowledge_qa","goal":"one standalone answer goal","expected_facts":["facts needed to answer this goal"],"depends_on":[]}}]}}

Available capability IDs: {json.dumps(routing["target_sub_agents"], ensure_ascii=False)}
User goal: {routing["intent"]["goal"]}

Rules:
- task_id must be unique and stable within this plan.
- depends_on may reference task_id only, never capability ID.
- The same capability may be used by multiple independent tasks.
- For knowledge_qa, split only genuinely independent answer goals, at most 3. Keep a simple request as one goal.
- Each knowledge_qa goal must be standalone, single-purpose, and preserve the user's objects, actions, conditions, and constraints.
- expected_facts describes the minimum facts needed to answer that goal; it is not a retrieval query.
- Do not create separate goals for synonyms or alternative query phrasings.
- Do not create tool arguments or unsupported capabilities.
""".strip()
    llm = (
        planner_llm_factory()
        if planner_llm_factory
        else get_llm_for_planner(temperature=0, max_tokens=500)
    )
    response = await llm.ainvoke(prompt)
    parsed = parse_llm_json_object(coerce_text(getattr(response, "content", response)))
    if not parsed:
        raise ValueError("Planner returned no valid JSON object")
    return _validate_steps(
        list(parsed.get("steps") or []),
        targets=set(routing["target_sub_agents"]),
    )


def build_plan_node(*, planner_llm_factory: Callable[[], Any] | None):
    async def plan_node(state: AgentState) -> dict[str, Any]:
        started_at = perf_counter()
        routing = state["routing"]
        targets = list(routing["target_sub_agents"])
        if routing["route_type"] == ROUTE_MULTI_SUB_AGENT:
            steps = await _plan_multi_agent(state, planner_llm_factory=planner_llm_factory)
        else:
            steps = [
                {
                    "task_id": "task_1",
                    "sub_agent_id": targets[0],
                    "goal": routing["intent"]["goal"] or state["input"]["query"],
                    "expected_facts": [],
                    "depends_on": [],
                }
            ]
        execution_mode = (
            "single"
            if len(steps) == 1
            else "parallel"
            if all(not step["depends_on"] for step in steps)
            else "dag"
        )
        plan = {
            "execution_mode": execution_mode,
            "steps": steps,
            "reason": routing["reason"],
        }
        log_node_info(
            workflow_id="agent",
            node_id="plan",
            node_name="规划任务",
            details={"执行模式": execution_mode, "步骤数": len(steps)},
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        return {"plan": plan}

    return plan_node
