"""Execution boundary around LangGraph."""

from __future__ import annotations

from typing import Any, AsyncIterator, Callable

from app.agents.main.graph import create_agent_graph
from app.agents.main.state import AgentInput, AgentState
from app.application.agent.tool_context import prepare_tool_context


class AgentRunner:
    """Prepare the authorized capability context and execute the Agent graph."""

    def __init__(
        self,
        *,
        graph: Any | None = None,
        llm_factory: Callable[[], Any] | None = None,
    ):
        self._graph = graph or create_agent_graph(llm_factory=llm_factory)

    async def invoke(self, agent_input: AgentInput) -> AgentState:
        prepared = {**agent_input, "tool_context": await prepare_tool_context(agent_input)}
        return await self._graph.ainvoke({"input": prepared})

    async def stream(self, agent_input: AgentInput) -> AsyncIterator[Any]:
        prepared = {**agent_input, "tool_context": await prepare_tool_context(agent_input)}
        async for chunk in self._graph.astream(
            {"input": prepared},
            stream_mode=["updates", "custom"],
            version="v2",
        ):
            yield chunk


_agent_runner: AgentRunner | None = None


def get_agent_runner() -> AgentRunner:
    global _agent_runner
    if _agent_runner is None:
        _agent_runner = AgentRunner()
    return _agent_runner
