"""LLM工厂：统一管理不同的大模型，支持多provider动态切换"""
from typing import Optional
from langchain_openai import ChatOpenAI
from loguru import logger

from app.core.config import config_registry


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
            model_type: 模型类型（如：long_text_understanding, code_generation等）
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


def get_llm_for_long_text(**kwargs) -> ChatOpenAI:
    """获取长文本理解模型（Kimi 128K）"""
    return llm_factory.get_llm("long_text_understanding", **kwargs)


def get_llm_for_content_gen(**kwargs) -> ChatOpenAI:
    """获取内容生成模型（Kimi）"""
    return llm_factory.get_llm("content_generation", **kwargs)


def get_llm_for_code_gen(**kwargs) -> ChatOpenAI:
    """获取代码生成模型（Deepseek）"""
    return llm_factory.get_llm("code_generation", **kwargs)


def get_llm_for_evaluation(**kwargs) -> ChatOpenAI:
    """获取快速评估模型（Deepseek）"""
    return llm_factory.get_llm("quick_evaluation", **kwargs)


def get_llm_for_extraction(**kwargs) -> ChatOpenAI:
    """获取结构化提取模型（Kimi）"""
    return llm_factory.get_llm("structured_extraction", **kwargs)


def get_llm_for_design(**kwargs) -> ChatOpenAI:
    """获取设计决策模型（Deepseek）"""
    return llm_factory.get_llm("design_decision", **kwargs)


def get_llm_for_detection(**kwargs) -> ChatOpenAI:
    """获取内容检测模型（Deepseek）"""
    return llm_factory.get_llm("content_detection", **kwargs)


def get_llm_for_validation(**kwargs) -> ChatOpenAI:
    """获取代码验证模型（Deepseek）"""
    return llm_factory.get_llm("code_validation", **kwargs)


# 兼容旧接口（保持向后兼容）
def get_smart_llm(**kwargs) -> ChatOpenAI:
    """获取智能模型（兼容接口，映射到long_text_understanding）"""
    return get_llm_for_long_text(**kwargs)


def get_fast_llm(**kwargs) -> ChatOpenAI:
    """获取快速模型（兼容接口，映射到code_generation）"""
    return get_llm_for_code_gen(**kwargs)


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


def get_llm(model_type: str = "smart", **kwargs) -> ChatOpenAI:
    """
    统一LLM获取接口
    
    Args:
        model_type: "smart" 或 "fast" 或 "deepseek" 或 "kimi"
        
    Returns:
        ChatOpenAI实例
    """
    if model_type in ["smart", "fast"]:
        return llm_factory.get_llm(model_type, **kwargs)
    elif model_type == "deepseek":
        return get_deepseek_llm(**kwargs)
    elif model_type == "kimi":
        return get_kimi_llm(**kwargs)
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")
