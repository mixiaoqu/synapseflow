"""迭代问答状态定义"""
from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph.message import add_messages


class IterativeQAState(TypedDict):
    """迭代问答状态"""
    messages: Annotated[List, add_messages]
    query: str
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
    confidence_score: float
    iteration: int
    max_iterations: int
    should_continue: bool
