"""LLM模块"""
from app.core.llm.factory import (
    get_llm,
    get_llm_for_long_text,
    get_llm_for_content_gen,
    get_llm_for_code_gen,
    get_llm_for_evaluation,
    get_llm_for_extraction,
    get_llm_for_design,
    get_llm_for_detection,
    get_llm_for_validation,
    get_smart_llm,
    get_fast_llm,
    get_deepseek_llm,
    get_kimi_llm,
    llm_factory
)

__all__ = [
    "get_llm",
    # 按任务类型
    "get_llm_for_long_text",
    "get_llm_for_content_gen",
    "get_llm_for_code_gen",
    "get_llm_for_evaluation",
    "get_llm_for_extraction",
    "get_llm_for_design",
    "get_llm_for_detection",
    "get_llm_for_validation",
    # 兼容接口
    "get_smart_llm",
    "get_fast_llm",
    "get_deepseek_llm",
    "get_kimi_llm",
    "llm_factory"
]
