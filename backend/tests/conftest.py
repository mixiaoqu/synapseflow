"""pytest配置文件"""
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.main import app


@pytest.fixture
def client():
    """测试客户端"""
    return TestClient(app)


@pytest.fixture
def sample_query():
    """示例查询"""
    return "什么是LangGraph？"


@pytest.fixture
def sample_document():
    """示例文档"""
    return """
# 测试文档

这是一个测试文档的内容。

## 第一节
内容1

## 第二节
内容2
"""


@pytest.fixture
def sample_requirements():
    """示例需求文档"""
    return """
创建一个产品落地页，包含：
- 导航栏（Logo和菜单）
- Hero区域（标题和CTA按钮）
- 三个特性展示
- 联系表单

风格：现代简约，蓝色主题
"""


@pytest.fixture
def scripted_agent_llm():
    class ScriptedAgentLlm:
        def __init__(self, responses=(), answer="已根据提供的材料完成回答。"):
            self.responses = list(responses)
            self.prompts = []
            self.schemas = []
            self.answer = answer
            self.answer_prompts = []

        def bind(self, **kwargs):
            assert kwargs["response_format"] == {"type": "json_object"}
            return self

        def bind_tools(self, schemas, **kwargs):
            self.schemas.append(schemas)
            return self

        async def ainvoke(self, messages):
            self.prompts.append(messages)
            response = self.responses.pop(0)
            return response(messages) if callable(response) else response

        async def astream(self, prompt):
            self.answer_prompts.append(prompt)
            yield AIMessage(content=self.answer)

    return ScriptedAgentLlm
