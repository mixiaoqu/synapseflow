"""
配置模块
- settings: 环境变量（.env）
- config_registry: YAML 配置（models、embedding、logging 等）
- PROJECT_ROOT, CONFIG_DIR: 路径常量
"""
from .loader import CONFIG_DIR, PROJECT_ROOT
from .registry import config_registry
from .settings import settings

__all__ = ["settings", "config_registry", "PROJECT_ROOT", "CONFIG_DIR"]
