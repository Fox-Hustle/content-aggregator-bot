# app/__main__.py

"""Точка входа приложения."""

import asyncio

from app.orchestrator import Orchestrator
from app.utils.logger import logger, setup_logger


async def main() -> None:
    """Главная функция приложения."""
    # Настройка логирования
    setup_logger()

    logger.info("=" * 60)
    logger.info("Запуск Content Aggregator Bot")
    logger.info("=" * 60)

    # Создание и запуск оркестратора
    orchestrator = Orchestrator()

    try:
        await orchestrator.initialize()
        await orchestrator.run()

    except KeyboardInterrupt:
        logger.info("Прервано пользователем")

    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")
        raise

    finally:
        logger.info("Приложение завершено")


def run_main():
    """Синхронная обертка для запуска async main (для entry points)"""

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run_main()
