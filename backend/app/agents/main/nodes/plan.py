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
职责：把已经明确的用户目标拆成最小可执行任务计划。

唯一任务：为每个独立目标选择一个可用能力，并声明真实存在的步骤依赖。
不要回答用户问题，不要设计检索表达，不要生成工具参数，也不要推测答案应包含哪些事实。

只返回 JSON：
{{"steps":[{{"task_id":"goal_1","sub_agent_id":"knowledge_qa","goal":"可独立执行的单一目标","depends_on":[]}}]}}

可用能力 ID：{json.dumps(routing["target_sub_agents"], ensure_ascii=False)}
用户目标：{routing["intent"]["goal"]}

决策边界：
- task_id 在本计划内必须唯一且稳定。
- sub_agent_id 只能使用可用能力 ID；depends_on 只能引用本计划中的 task_id。
- 只有目标之间确实存在结果依赖时才填写 depends_on，否则保持空数组。
- 同一能力可以处理多个相互独立的目标。
- 仅拆分用户明确提出且可独立回答的目标；简单请求保持一个任务，不因同义表达或不同检索方式拆分。
- knowledge_qa 最多拆成 3 个目标；每个目标必须保留用户明确给出的对象、动作、条件和约束。
- 不补充用户没有提出的子目标、答案范围或完成标准。
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
