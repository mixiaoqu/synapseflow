"""迭代问答路由函数"""
from app.agents.states import IterativeQAState


def should_continue_iteration(state: IterativeQAState) -> str:
    """路由函数：决定下一步走向。继续则回到提问优化，否则结束"""
    if state.get("should_continue", False):
        return "query_optimizer"
    return "end"
