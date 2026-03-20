"""迭代问答状态定义"""
from typing import TypedDict, List, Dict, Any, Annotated, Optional
from langgraph.graph.message import add_messages


class IterativeQAState(TypedDict, total=False):
    """迭代问答状态"""
    messages: Annotated[List, add_messages] # 对话历史
    query: str # 用户原始问题
    optimized_query: str # 优化后的问题
    collection_id: Optional[int]  # 限定检索范围
    retrieved_docs: List[Dict[str, Any]] # 检索结果
    context: str # 上下文
    answer: str # 答案
    confidence_score: float # 置信度
    iteration: int # 迭代次数
    max_iterations: int # 最大迭代次数
    should_continue: bool # 是否继续迭代
    iteration_history: List[Dict[str, Any]] # 迭代历史
    last_evaluation_feedback: Optional[Dict[str, Any]] # 最后一次评估反馈
    document_issues: List[Dict[str, Any]]  # 跨轮累积的文档问题记录
