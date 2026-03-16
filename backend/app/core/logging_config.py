"""
Loguru 日志配置
从 config/logging.yaml 加载配置，支持 .env 覆盖
"""
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.core.config.loader import load_logging_raw, PROJECT_ROOT


def setup_logging() -> None:
    """配置 Loguru，应用启动时调用"""
    config = load_logging_raw()
    log_cfg = config.get("logging", config) or {}

    level = settings.LOG_LEVEL or log_cfg.get("level", "INFO")
    to_file = settings.LOG_TO_FILE if settings.LOG_TO_FILE is not None else log_cfg.get("to_file", True)
    use_json = settings.LOG_JSON if settings.LOG_JSON is not None else log_cfg.get("json", False)

    # 移除默认 handler，使用自定义配置
    logger.remove()

    # 控制台输出
    fmt = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    if use_json:
        fmt = "{message}"
    logger.add(
        sys.stderr,
        format=fmt,
        level=level,
        colorize=not use_json,
    )

    # 文件输出
    if to_file:
        file_cfg = log_cfg.get("file", {})
        log_path = file_cfg.get("path", "logs/synapseflow.log")
        if not Path(log_path).is_absolute():
            log_path = PROJECT_ROOT / log_path
        log_file = Path(log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        rotation = file_cfg.get("rotation", "10 MB")
        retention = file_cfg.get("retention", "7 days")

        logger.add(
            str(log_file),
            format=fmt,
            level=level,
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
        )

    diagnose = settings.LOG_DIAGNOSE if settings.LOG_DIAGNOSE is not None else log_cfg.get("diagnose", False)
    logger.configure(extra={"diagnose": diagnose})
