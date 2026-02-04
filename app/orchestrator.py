# app/orchestrator.py

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import yaml

from app.config import settings
from app.database import PostRepository
from app.models.content import Post
from app.publishers.telegram import TelegramPublisher
from app.scrapers import BaseScraper, ScraperFactory
from app.utils.logger import logger


class SourceConfig:
    def __init__(self, type: str, url: str, enabled: bool = True):
        self.type = type
        self.url = url
        self.enabled = enabled

    def __repr__(self) -> str:
        status = "✓" if self.enabled else "✗"
        return f"SourceConfig({status} {self.type}: {self.url})"


class Orchestrator:
    def __init__(self):
        self.repository = PostRepository(settings.database_url)
        self.publisher = TelegramPublisher()
        self.scrapers: list[BaseScraper] = []
        self.running = False
        # Запоминаем время запуска (в UTC, так как Telegram отдает время в UTC)
        self.start_time = datetime.now(timezone.utc)

    async def initialize(self) -> None:
        logger.info("Инициализация оркестратора...")
        settings.ensure_directories()
        await self.repository.init_db()
        await self.publisher.initialize()
        await self._load_sources()
        logger.info(
            f"Оркестратор готов. Режим: только посты новее {self.start_time.strftime('%H:%M:%S')}"
        )

    async def _load_sources(self) -> None:
        config_path = settings.sources_config
        if not config_path.exists():
            self._create_example_config(config_path)
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            for source_data in config.get("sources", []):
                source = SourceConfig(
                    type=source_data.get("type", ""),
                    url=source_data.get("url", ""),
                    enabled=source_data.get("enabled", True),
                )
                if not source.enabled:
                    continue

                try:
                    scraper = ScraperFactory.create_scraper(source.type, source.url)
                    self.scrapers.append(scraper)
                except ValueError as e:
                    logger.error(f"Ошибка источника {source.url}: {e}")

        except Exception as e:
            logger.error(f"Ошибка конфига: {e}")

    def _create_example_config(self, path: Path) -> None:
        # (Код создания конфига пропущен для краткости, он есть в оригинале)
        pass

    async def run(self) -> None:
        if not self.scrapers:
            logger.error("Нет источников!")
            return

        self.running = True
        logger.info("Запуск цикла...")

        try:
            while self.running:
                await self._scrape_and_publish_cycle()
                logger.info(f"Ожидание {settings.scrape_interval_seconds}s...")
                await asyncio.sleep(settings.scrape_interval_seconds)
        except KeyboardInterrupt:
            self.running = False
        finally:
            await self.shutdown()

    async def _scrape_and_publish_cycle(self) -> None:
        logger.info("=== Сбор данных ===")

        # Собираем данные (с ограничением в 2 поста для скорости, можно вернуть 10)
        scrape_tasks = [
            scraper.scrape(limit=1, since_time=self.start_time)
            for scraper in self.scrapers
        ]
        results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

        all_posts: list[Post] = []
        for res in results:
            if isinstance(res, list):
                all_posts.extend(res)

        logger.info(f"Найдено постов: {len(all_posts)}")

        new_count = 0
        published_count = 0
        skipped_old_count = 0

        for post in all_posts:
            # 1. Проверка на дубликаты в БД
            if await self.repository.is_post_processed(post.content_hash):
                continue

            # Сохраняем как "обработанный"
            await self.repository.mark_post_processed(post)
            new_count += 1

            # 2. ФИЛЬТР: Если пост старый (создан до запуска бота)
            # Приводим дату поста к UTC для корректного сравнения
            post_date = post.created_at
            if post_date.tzinfo is None:
                post_date = post_date.replace(tzinfo=timezone.utc)

            if post_date < self.start_time:
                logger.debug(f"Пропущен старый пост: {post.url} ({post_date})")
                skipped_old_count += 1
                continue

            # 3. Если пост новый - публикуем
            logger.info(
                f"НОВЫЙ ПОСТ: {post.url}. Публикация через {settings.post_check_delay_seconds}с..."
            )
            await asyncio.sleep(settings.post_check_delay_seconds)

            try:
                msg_id = await self.publisher.publish_post(post)
                await self.repository.mark_post_published(post.content_hash, msg_id)
                published_count += 1
                logger.success(f"Опубликовано: {post.url}")
            except Exception as e:
                await self.repository.mark_post_failed(post.content_hash, str(e))
                logger.error(f"Ошибка публикации {post.url}: {e}")

        logger.info(
            f"Итог цикла: Новых в базе={new_count}, Опубликовано={published_count}, Пропущено старых={skipped_old_count}"
        )

    async def shutdown(self) -> None:
        logger.info("Выключение...")
        for s in self.scrapers:
            await s.close()
        await self.publisher.close()
        await self.repository.close()
