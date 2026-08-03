"""Factory helpers for chat LLM instances."""

from langchain_openai import ChatOpenAI
from loguru import logger

from app.core.config import config_registry


class LLMFactory:
    """Build chat LLM instances from logical roles or concrete model assets."""

    def get_llm(self, model_type: str, **override_kwargs) -> ChatOpenAI:
        """Build an LLM using a logical system role such as `generation`."""
        model_config = config_registry.get_model_config(model_type)
        return self._build_chat_openai(model_config, **override_kwargs)

    def get_llm_for_asset(self, asset_key: str, **override_kwargs) -> ChatOpenAI:
        """Build an LLM using a concrete model asset key."""
        model_config = config_registry.get_model_asset(asset_key)
        return self._build_chat_openai(model_config, **override_kwargs)

    @staticmethod
    def _build_chat_openai(model_config, **override_kwargs) -> ChatOpenAI:
        llm_kwargs = {
            "base_url": model_config.api_base,
            "api_key": model_config.api_key,
            "model": model_config.model,
            "timeout": model_config.request_timeout,
            "streaming": model_config.streaming,
        }
        if model_config.temperature is not None:
            llm_kwargs["temperature"] = model_config.temperature
        if model_config.max_tokens is not None:
            llm_kwargs["max_tokens"] = model_config.max_tokens

        llm_kwargs.update(override_kwargs)
        if getattr(model_config, "provider", "") == "deepseek":
            extra_body = dict(llm_kwargs.get("extra_body") or {})
            thinking = dict(extra_body.get("thinking") or {})
            thinking["type"] = "disabled"
            extra_body["thinking"] = thinking
            llm_kwargs["extra_body"] = extra_body
        logger.debug(
            "Creating LLM instance: key={} provider={} model={}",
            getattr(model_config, "key", "unknown"),
            getattr(model_config, "provider", "unknown"),
            llm_kwargs.get("model"),
        )
        return ChatOpenAI(**llm_kwargs)


llm_factory = LLMFactory()


def get_llm_for_planner(**kwargs) -> ChatOpenAI:
    return llm_factory.get_llm("planner", **kwargs)


def get_llm_for_analysis(**kwargs) -> ChatOpenAI:
    return llm_factory.get_llm("analysis", **kwargs)


def get_llm_for_generation(**kwargs) -> ChatOpenAI:
    return llm_factory.get_llm("generation", **kwargs)


def get_llm_for_tool(**kwargs) -> ChatOpenAI:
    return llm_factory.get_llm("tool", **kwargs)


def get_llm_for_asset(asset_key: str, **kwargs) -> ChatOpenAI:
    return llm_factory.get_llm_for_asset(asset_key, **kwargs)


def get_smart_llm(**kwargs) -> ChatOpenAI:
    return get_llm_for_analysis(**kwargs)


def get_fast_llm(**kwargs) -> ChatOpenAI:
    return get_llm_for_generation(**kwargs)


def get_llm(model_type: str = "analysis", **kwargs) -> ChatOpenAI:
    """Unified accessor for logical roles or concrete asset keys."""
    if model_type == "smart":
        return get_llm_for_analysis(**kwargs)
    if model_type == "fast":
        return get_llm_for_generation(**kwargs)

    if model_type in ("planner", "analysis", "generation", "tool"):
        return llm_factory.get_llm(model_type, **kwargs)

    return llm_factory.get_llm_for_asset(model_type, **kwargs)
