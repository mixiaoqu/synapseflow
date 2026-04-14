"""JSON解析工具函数"""
import json
import re
from typing import Any, Dict


def extract_json_from_llm_response(content: str) -> Dict[str, Any]:
    """
    从LLM回复中提取JSON对象。
    
    支持以下格式：
    - 纯JSON字符串
    - ```json ... ``` 代码块
    - ``` ... ``` 代码块
    - 文本中嵌入的JSON对象
    
    Args:
        content: LLM的原始回复内容
        
    Returns:
        解析后的字典，解析失败返回空字典
    """
    content = (content or "").strip()
    if not content:
        return {}
    
    # 尝试直接解析
    try:
        return json.loads(content)
    except Exception:
        pass
    
    # 尝试提取 ```json ... ``` 代码块
    if "```json" in content:
        match = re.search(r"```json\s*([\s\S]*?)```", content)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except Exception:
                pass
    
    # 尝试提取 ``` ... ``` 代码块
    if "```" in content:
        match = re.search(r"```\s*([\s\S]*?)```", content)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except Exception:
                pass
    
    # 尝试提取文本中的JSON对象
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    
    return {}
