"""
智能体工具目录

存放可供智能体使用的工具函数（用于ReAct模式）。

示例：
    from langchain_core.tools import tool
    
    @tool
    def search_knowledge_base(query: str) -> str:
        '''搜索知识库'''
        return vectorstore.search(query)
"""
