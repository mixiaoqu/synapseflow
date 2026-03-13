"""
配置加载器：纯 I/O 逻辑
负责读取 YAML、${VAR} 环境变量替换，返回原始 dict
"""
import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DOTENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(DOTENV_PATH)


def load_yaml(path: Path, default: Any = None) -> Dict[str, Any]:
    """加载 YAML 文件"""
    if not path.exists():
        return default or {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def substitute_env(text: str) -> str:
    """将 ${VAR} 替换为 os.environ 中的值"""
    if not isinstance(text, str):
        return text

    def repl(match: re.Match) -> str:
        key = match.group(1)
        return os.environ.get(key, match.group(0))

    return re.sub(r"\$\{(\w+)\}", repl, text)


def substitute_env_deep(obj: Any) -> Any:
    """递归对字符串进行 env 替换"""
    if isinstance(obj, str):
        return substitute_env(obj)
    if isinstance(obj, dict):
        return {k: substitute_env_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_env_deep(v) for v in obj]
    return obj


def load_models_raw() -> Dict[str, Any]:
    """加载 models.yaml 原始内容"""
    return load_yaml(CONFIG_DIR / "models.yaml", {})


def load_embedding_raw() -> Dict[str, Any]:
    """加载 embedding.yaml 原始内容"""
    return load_yaml(CONFIG_DIR / "embedding.yaml", {})


def load_logging_raw() -> Dict[str, Any]:
    """加载 logging.yaml 原始内容"""
    return load_yaml(CONFIG_DIR / "logging.yaml", {})


def load_repositories_raw() -> Dict[str, Any]:
    """加载 repositories.yaml，并执行 ${VAR} 替换"""
    data = load_yaml(CONFIG_DIR / "repositories.yaml", {"repositories": [], "defaults": {}})
    return substitute_env_deep(data)


def load_prompt_templates_raw() -> Dict[str, str]:
    """加载 prompt_templates.yaml 原始内容"""
    data = load_yaml(CONFIG_DIR / "prompt_templates.yaml", {})
    return data.get("templates", {})
