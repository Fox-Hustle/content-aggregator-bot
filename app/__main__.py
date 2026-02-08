# app/__main__.py

import asyncio
import argparse
from app.orchestrator import Orchestrator
from app.utils.logger import logger, setup_logger, LogLevel


def parse_args():
    parser = argparse.ArgumentParser(
        description="Content Aggregator Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Примеры использования:
            python -m app                      # Обычный запуск (INFO в консоль)
            python -m app --quiet              # Только ошибки в консоль
            python -m app --verbose            # Вся отладка в консоль
            python -m app --no-file            # Без записи в файл
            python -m app --level WARNING      # Кастомный уровень
        """,
    )

    parser.add_argument(
        "--level",
        choices=["ERROR", "WARNING", "INFO", "DEBUG"],
        help="Уровень логирования для консоли",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Только ошибки в консоль (эквивалент --level ERROR)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Вся отладка в консоль (эквивалент --level DEBUG)",
    )

    parser.add_argument(
        "--no-file", action="store_true", help="Отключить запись логов в файл"
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    console_level = None
    if args.quiet:
        console_level = LogLevel.ERROR
    elif args.verbose:
        console_level = LogLevel.DEBUG
    elif args.level:
        console_level = args.level

    file_enabled = not args.no_file

    setup_logger(console_level=console_level, file_enabled=file_enabled)

    logger.info("=" * 60)
    logger.info("Content Aggregator Bot")
    logger.info("=" * 60)

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
        logger.info("Завершено")


def run_main():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run_main()
