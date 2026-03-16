"""修订相关状态定义（用户建议驱动）"""
from typing import TypedDict, List, Dict, Any, Optional


class UserDrivenRevisionState(TypedDict):
    """用户建议驱动修订状态"""
    original_doc: str
    current_doc: str
    user_suggestions: str
    parsed_tasks: List[Dict[str, Any]]
    doc_structure: List[Dict[str, Any]]
    chunks_meta: List[Any]  # [(chunk_text, section_title, index), ...]
    chunks_positions: List[Any]  # [(start, end), ...]
    affected_chunk_indices: List[int]
    section_hints: Dict[int, str]  # {chunk_idx: "本块相关任务: ..."}
    revised_document: str
    doc_id: Optional[int]
