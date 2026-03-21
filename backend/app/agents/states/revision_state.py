"""修订相关状态定义（用户建议驱动）"""
from typing import TypedDict, List, Dict, Any, Optional


class UserDrivenRevisionState(TypedDict):
    """用户建议驱动修订状态"""
    original_doc: str # 原始文档
    current_doc: str # 当前文档
    user_suggestions: str # 用户建议
    parsed_tasks: List[Dict[str, Any]] # 解析后的任务
    doc_structure: List[Dict[str, Any]] # 文档结构
    chunks_meta: List[Any]  # 块元数据
    chunks_positions: List[Any]  # 块位置
    affected_chunk_indices: List[int] # 受影响的块索引
    section_hints: Dict[int, str]  # 块提示
    revised_document: str # 修订后的文档
    doc_id: Optional[int] # 文档ID
