"""
通用工具

与业务无关的辅助工具，可被任意智能体复用。
"""
from datetime import datetime
from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """获取当前日期和时间，用于需要时效性的回答。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def calculate(expression: str) -> str:
    """
    执行简单数学计算，支持 +、-、*、/、( )。
    仅接受数字和运算符，禁止执行任意代码。
    """
    import re
    allowed = set("0123456789+-*/(). ")
    if not all(c in allowed for c in expression):
        return "错误：仅支持数字和 + - * / ( )"
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"计算错误: {e}"
