"""能力调用与内部查询共享的单次运行预算。"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import monotonic
from typing import Iterator


@dataclass(frozen=True)
class AgentLimits:
    max_rounds: int = 6
    max_calls: int = 8
    max_operations: int = 24
    max_parallel: int = 3
    call_timeout: float = 90
    model_timeout: float = 60
    run_timeout: float = 240

    def __post_init__(self):
        if any(value <= 0 for value in vars(self).values()):
            raise ValueError("Agent 预算必须为正数")


class ExecutionBudgetExceededError(RuntimeError):
    pass


@dataclass
class ExecutionBudget:
    limit: int
    deadline: float
    used: int = 0

    def consume(self) -> None:
        if self.used >= self.limit or monotonic() >= self.deadline:
            raise ExecutionBudgetExceededError("本次任务已达到执行预算")
        self.used += 1


_current_budget: ContextVar[ExecutionBudget | None] = ContextVar("agent_budget", default=None)


@contextmanager
def execution_budget(budget: ExecutionBudget) -> Iterator[None]:
    token = _current_budget.set(budget)
    try:
        yield
    finally:
        _current_budget.reset(token)


def consume_operation() -> None:
    budget = _current_budget.get()
    if budget is not None:
        budget.consume()
