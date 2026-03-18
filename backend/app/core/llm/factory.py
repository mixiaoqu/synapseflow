"""LLM工厂：统一管理不同的大模型，支持多provider动态切换"""
import os
from typing import Optional
from langchain_openai import ChatOpenAI
from loguru import logger

from app.core.config import config_registry


# 模型类型：planner | analysis | generation | tool（embedding/rerank 使用独立API）
class LLMFactory:
    """LLM工厂类，使用config_registry获取模型配置"""
    
    def get_llm(
        self,
        model_type: str,
        **override_kwargs
    ) -> ChatOpenAI:
        """
        获取LLM实例

        Args:
            model_type: 模型类型（planner | analysis | generation | tool）
            override_kwargs: 覆盖默认配置的参数

        Returns:
            ChatOpenAI实例
        """
        # 从registry获取配置（已包含验证和API密钥）
        model_config = config_registry.get_model_config(model_type)
        
        # 构建LLM参数
        llm_kwargs = {
            "base_url": model_config["api_base"],
            "api_key": model_config["api_key"],
            "model": model_config["model"],
            "temperature": model_config["temperature"],
            "timeout": model_config["request_timeout"],
            "streaming": model_config["streaming"],
        }
        
        # 仅当 max_tokens 有值时传入，None 表示不限制输出长度
        if model_config.get("max_tokens") is not None:
            llm_kwargs["max_tokens"] = model_config["max_tokens"]
        
        # 应用覆盖参数
        llm_kwargs.update(override_kwargs)

        logger.debug("创建LLM实例: model_type={}, model={}", model_type, llm_kwargs.get("model"))
        return ChatOpenAI(**llm_kwargs)


# 创建全局工厂实例
llm_factory = LLMFactory()


def get_llm_for_planner(**kwargs) -> ChatOpenAI:
    """获取规划任务模型（planner）"""
    return llm_factory.get_llm("planner", **kwargs)


def get_llm_for_analysis(**kwargs) -> ChatOpenAI:
    """获取分析理解模型（analysis）"""
    return llm_factory.get_llm("analysis", **kwargs)


def get_llm_for_generation(**kwargs) -> ChatOpenAI:
    """获取生成内容模型（generation）"""
    return llm_factory.get_llm("generation", **kwargs)


def get_llm_for_tool(**kwargs) -> ChatOpenAI:
    """获取工具调用模型（tool）"""
    return llm_factory.get_llm("tool", **kwargs)


# 兼容旧接口
def get_smart_llm(**kwargs) -> ChatOpenAI:
    """获取智能模型（兼容接口，映射到 analysis）"""
    return get_llm_for_analysis(**kwargs)


def get_fast_llm(**kwargs) -> ChatOpenAI:
    """获取快速模型（兼容接口，映射到 generation）"""
    return get_llm_for_generation(**kwargs)


def get_deepseek_llm(**kwargs) -> ChatOpenAI:
    """
    直接获取Deepseek模型（兼容旧代码）
    """
    return ChatOpenAI(
        base_url="https://api.deepseek.com/v1",
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        model="deepseek-chat",
        temperature=kwargs.get("temperature", 0.3),
        timeout=kwargs.get("timeout", 120),
        **kwargs
    )


def get_kimi_llm(**kwargs) -> ChatOpenAI:
    """
    直接获取Kimi模型（兼容旧代码）
    """
    return ChatOpenAI(
        base_url="https://api.moonshot.cn/v1",
        api_key=os.getenv("KIMI_API_KEY", ""),
        model="moonshot-v1-128k",
        temperature=kwargs.get("temperature", 0.2),
        timeout=kwargs.get("timeout", 180),
        **kwargs
    )


def get_llm(model_type: str = "analysis", **kwargs) -> ChatOpenAI:
    """
    统一LLM获取接口

    Args:
        model_type: planner | analysis | generation | tool | smart | fast | deepseek | kimi

    Returns:
        ChatOpenAI实例
    """
    if model_type == "smart":
        return get_llm_for_analysis(**kwargs)
    elif model_type == "fast":
        return get_llm_for_generation(**kwargs)
    elif model_type in ("planner", "analysis", "generation", "tool"):
        return llm_factory.get_llm(model_type, **kwargs)
    elif model_type == "deepseek":
        return get_deepseek_llm(**kwargs)
    elif model_type == "kimi":
        return get_kimi_llm(**kwargs)
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")
