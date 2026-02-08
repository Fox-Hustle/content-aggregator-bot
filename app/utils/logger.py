# app/utils/logger.py

import sys
from pathlib import Path
from loguru import logger
from app.config import settings


class LogLevel:
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


def setup_logger(console_level: str | None = None, file_enabled: bool = True) -> None:
    logger.remove()
    effective_console_level = console_level or settings.log_level

    console_format = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <7}</level> | "
        "<level>{message}</level>"
    )

    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    logger.add(
        sys.stderr,
        format=console_format,
        level=effective_console_level,
        colorize=True,
        backtrace=False,
        diagnose=False,
    )

    if file_enabled:
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            settings.log_file,
            format=file_format,
            level="DEBUG",
            rotation="10 MB",
            retention="1 week",
            compression="zip",
            backtrace=True,
            diagnose=True,
            encoding="utf-8",
        )


__all__ = ["logger", "setup_logger", "LogLevel"]
