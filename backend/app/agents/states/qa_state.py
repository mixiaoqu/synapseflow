"""迭代问答状态定义"""
from typing import TypedDict, List, Dict, Any, Annotated, Optional
from langgraph.graph.message import add_messages


class IterativeQAState(TypedDict, total=False):
    """迭代问答状态"""
    messages: Annotated[List, add_messages]
    query: str
    optimized_query: str
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
    confidence_score: float
    iteration: int
    max_iterations: int
    should_continue: bool
    iteration_history: List[Dict[str, Any]]
    last_evaluation_feedback: Optional[Dict[str, Any]]
