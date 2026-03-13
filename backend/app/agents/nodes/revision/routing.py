"""递归修订路由函数"""
from app.agents.states.revision_state import RecursiveRevisionState


def should_continue_revision(state: RecursiveRevisionState) -> str:
    """决定是否继续修订"""
    if state.get('is_complete', False):
        return "end"
    return "detect_missing"
