# app/utils/logger.py

"""Настройка системы логирования."""

import sys

from loguru import logger

from app.config import settings


def setup_logger() -> None:
    """Настраивает систему логирования для приложения."""
    # Удаляем стандартный обработчик
    logger.remove()

    # Формат для консоли (более читаемый)
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Формат для файла (более подробный)
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    # Консольный вывод
    logger.add(
        sys.stderr,
        format=console_format,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Файловый вывод с ротацией
    logger.add(
        settings.log_file,
        format=file_format,
        level=settings.log_level,
        rotation="10 MB",  # Новый файл при достижении 10 МБ
        retention="1 week",  # Хранить логи неделю
        compression="zip",  # Сжимать старые логи
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
    )

    logger.info("Система логирования инициализирована")
    logger.debug(f"Уровень логирования: {settings.log_level}")
    logger.debug(f"Файл логов: {settings.log_file}")


# Для удобного импорта
__all__ = ["logger", "setup_logger"]
