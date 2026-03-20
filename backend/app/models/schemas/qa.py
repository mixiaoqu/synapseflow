"""问答相关Schema"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class QARequest(BaseModel):
    """问答请求"""
    query: str = Field(..., description="用户问题")
    max_iterations: int = Field(default=3, ge=1, le=5, description="最大迭代次数")
    session_id: Optional[str] = Field(None, description="会话ID")
    collection_id: Optional[int] = Field(None, description="限定检索集合，空则检索全部")


class IterationRecord(BaseModel):
    """单轮迭代记录"""
    round: int
    question: str
    original_question: str
    answer: str
    score: float
    passed: bool
    reason: Optional[str] = None
    suggestion: Optional[str] = None


class QAResponse(BaseModel):
    """问答响应"""
    answer: str = Field(..., description="答案")
    confidence_score: float = Field(..., description="置信度分数")
    iteration: int = Field(..., description="实际迭代次数")
    retrieved_docs: List[Dict[str, Any]] = Field(default_factory=list, description="检索到的文档")
    iteration_history: List[Dict[str, Any]] = Field(default_factory=list, description="迭代历史记录")
    document_issues: List[Dict[str, Any]] = Field(
        default_factory=list, description="文档问题记录，作为文档修改建议"
    )
    session_id: Optional[str] = None
