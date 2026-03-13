"""
提示词模板目录

存放所有LLM提示词模板，便于统一管理和优化。

示例：
    from langchain.prompts import ChatPromptTemplate
    
    QA_PROMPT = ChatPromptTemplate.from_messages([
        ("system", "你是问答助手..."),
        ("user", "{query}")
    ])
"""
