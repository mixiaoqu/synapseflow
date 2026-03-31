"""
Configuration loader: keeps raw file I/O separate from config parsing.
Responsible for reading YAML files, expanding `${VAR}` placeholders,
and returning plain dictionaries.
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
    """Load a YAML file."""
    if not path.exists():
        return default or {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def substitute_env(text: str) -> str:
    """Replace `${VAR}` placeholders with values from `os.environ`."""
    if not isinstance(text, str):
        return text

    def repl(match: re.Match) -> str:
        key = match.group(1)
        return os.environ.get(key, match.group(0))

    return re.sub(r"\$\{(\w+)\}", repl, text)


def substitute_env_deep(obj: Any) -> Any:
    """Recursively apply environment substitution to strings."""
    if isinstance(obj, str):
        return substitute_env(obj)
    if isinstance(obj, dict):
        return {k: substitute_env_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_env_deep(v) for v in obj]
    return obj


def load_models_raw() -> Dict[str, Any]:
    """Load raw contents of `models.yaml`."""
    return load_yaml(CONFIG_DIR / "models.yaml", {})


def load_app_raw() -> Dict[str, Any]:
    """Load raw contents of `app.yaml`."""
    return load_yaml(CONFIG_DIR / "app.yaml", {})


def load_embedding_raw() -> Dict[str, Any]:
    """Load raw contents of `embedding.yaml`."""
    return load_yaml(CONFIG_DIR / "embedding.yaml", {})


def load_rerank_raw() -> Dict[str, Any]:
    """Load raw contents of `rerank.yaml`."""
    return load_yaml(CONFIG_DIR / "rerank.yaml", {})


def load_logging_raw() -> Dict[str, Any]:
    """Load raw contents of `logging.yaml`."""
    return load_yaml(CONFIG_DIR / "logging.yaml", {})


def load_repositories_raw() -> Dict[str, Any]:
    """Load `repositories.yaml` and expand `${VAR}` placeholders."""
    data = load_yaml(CONFIG_DIR / "repositories.yaml", {"repositories": [], "defaults": {}})
    return substitute_env_deep(data)
