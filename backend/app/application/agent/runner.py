"""Execution boundary around LangGraph."""

from __future__ import annotations

from typing import Any, AsyncIterator, Callable

from app.agents.main.graph import create_agent_graph
from app.agents.main.state import AgentInput, AgentState


class AgentRunner:
    """Run one prepared Agent input without product or persistence concerns."""

    def __init__(
        self,
        *,
        graph: Any | None = None,
        llm_factory: Callable[[], Any] | None = None,
    ):
        self._graph = graph or create_agent_graph(llm_factory=llm_factory)

    async def invoke(self, agent_input: AgentInput) -> AgentState:
        return await self._graph.ainvoke({"input": agent_input})

    def stream(self, agent_input: AgentInput) -> AsyncIterator[Any]:
        return self._graph.astream(
            {"input": agent_input},
            stream_mode=["updates", "custom"],
            version="v2",
        )


_agent_runner: AgentRunner | None = None


def get_agent_runner() -> AgentRunner:
    global _agent_runner
    if _agent_runner is None:
        _agent_runner = AgentRunner()
    return _agent_runner
