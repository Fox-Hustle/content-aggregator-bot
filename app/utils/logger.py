# app/utils/logger.py

import sys

from loguru import logger

from app.config import settings


def setup_logger() -> None:
    logger.remove()

    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
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
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    logger.add(
        settings.log_file,
        format=file_format,
        level=settings.log_level,
        rotation="10 MB",
        retention="1 week",
        compression="zip",
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
    )

    logger.info("Система логирования инициализирована")
    logger.debug(f"Уровень логирования: {settings.log_level}")
    logger.debug(f"Файл логов: {settings.log_file}")


__all__ = ["logger", "setup_logger"]
