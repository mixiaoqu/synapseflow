"""
Loguru 日志配置
从 config/logging.yaml 加载配置，支持 .env 覆盖
"""
import sys
from pathlib import Path

from loguru import logger

from app.core.config import config_registry
from app.core.config.loader import PROJECT_ROOT


def setup_logging() -> None:
    """配置 Loguru，应用启动时调用"""
    log_cfg = config_registry.get_logging_config()

    level = log_cfg.level
    to_file = log_cfg.log_to_file
    use_json = log_cfg.json

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
        file_cfg = log_cfg.file
        log_path = file_cfg.path
        if not Path(log_path).is_absolute():
            log_path = PROJECT_ROOT / log_path
        log_file = Path(log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        rotation = file_cfg.rotation
        retention = file_cfg.retention

        logger.add(
            str(log_file),
            format=fmt,
            level=level,
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
        )

    diagnose = log_cfg.diagnose
    logger.configure(extra={"diagnose": diagnose})
