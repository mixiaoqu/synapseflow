"""
配置注册表：持有并解析配置
使用 Loader 加载原始数据，按业务逻辑解析后通过专用方法暴露
"""
import os
from typing import Dict, Any

from .loader import (
    load_models_raw,
    load_embedding_raw,
    load_logging_raw,
    load_repositories_raw,
    load_prompt_templates_raw,
)
from .settings import settings


class ConfigRegistry:
    """配置注册表，提供解析后的配置访问"""

    def get_model_config(self, model_type: str) -> Dict[str, Any]:
        """获取指定模型类型的配置（config/models.yaml）"""
        data = load_models_raw()
        models_cfg = data.get("models", {})
        providers_cfg = data.get("providers", {})
        api_keys_mapping = data.get("api_keys", {})
        
        raw = models_cfg.get(model_type, {})
        if not raw:
            raise ValueError(f"模型类型 '{model_type}' 未在 models.yaml 中定义")

        provider_id = raw.get("provider")
        if not provider_id:
            raise ValueError(f"模型 '{model_type}' 未配置 provider")
        
        provider = providers_cfg.get(provider_id, {})
        if not provider:
            raise ValueError(f"Provider '{provider_id}' 未在 providers 中定义")

        # 从 api_keys 映射获取环境变量名
        api_key_env_name = api_keys_mapping.get(provider_id)
        api_key = os.environ.get(api_key_env_name, "") if api_key_env_name else ""
        
        if not api_key:
            raise ValueError(f"Provider '{provider_id}' 的API密钥未设置（环境变量：{api_key_env_name}）")

        return {
            "model": raw.get("model", "gpt-4"),
            "name": raw.get("name", model_type),
            "api_key": api_key,
            "api_base": provider.get("api_base", ""),
            "temperature": raw.get("temperature", 0.7),
            "request_timeout": raw.get("request_timeout", 120),
            "streaming": raw.get("streaming", True),
            "max_tokens": raw.get("max_tokens"),  # None 表示不限制，由 API 使用模型默认最大值
        }

    def get_embedding_config(self) -> Dict[str, Any]:
        """获取向量嵌入配置（config/embedding.yaml）"""
        data = load_embedding_raw()
        emb = data.get("embedding", {})
        return {
            "model": emb.get("model", "BAAI/bge-small-zh-v1.5"),
            "dim": int(emb.get("dim", 512)),
        }

    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置（config/logging.yaml，.env 可覆盖）"""
        data = load_logging_raw()
        defaults = {"level": "INFO", "json": False, "to_file": True, "diagnose": False}
        defaults.update(data.get("logging", {}))
        return {
            "level": settings.LOG_LEVEL or defaults["level"],
            "json_logs": settings.LOG_JSON if settings.LOG_JSON is not None else defaults["json"],
            "log_to_file": settings.LOG_TO_FILE if settings.LOG_TO_FILE is not None else defaults["to_file"],
            "diagnose": settings.LOG_DIAGNOSE if settings.LOG_DIAGNOSE is not None else defaults["diagnose"],
        }

    def get_repositories_config(self) -> Dict[str, Any]:
        """获取仓库配置（config/repositories.yaml，支持 ${VAR}）"""
        return load_repositories_raw()

    def get_prompt_templates(self) -> Dict[str, str]:
        """获取 prompt 模板（config/prompt_templates.yaml）"""
        return load_prompt_templates_raw()

    def get_scenario_mapping(self) -> Dict[str, Dict[str, str]]:
        """获取场景与模型的映射关系（config/models.yaml）"""
        data = load_models_raw()
        return data.get("scenario_model_mapping", {})

    @property
    def llm_configured(self) -> bool:
        """是否已配置 LLM provider 的 api_key"""
        data = load_models_raw()
        api_keys_mapping = data.get("api_keys", {})
        for provider_id, env_var_name in api_keys_mapping.items():
            if os.environ.get(env_var_name, "").strip():
                return True
        return False


config_registry = ConfigRegistry()
