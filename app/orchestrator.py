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
        return f"{status} {self.type}: {self.url}"


class Orchestrator:
    def __init__(self):
        self.repository = PostRepository(settings.database_url)
        self.publisher = TelegramPublisher()
        self.scrapers: list[BaseScraper] = []
        self.running = False
        self.start_time = datetime.now(timezone.utc)
        self.cycle_errors = 0
        self.max_consecutive_errors = 5

    async def initialize(self) -> None:
        logger.info("🚀 Инициализация...")
        settings.ensure_directories()

        try:
            await self.repository.init_db()
            await self.publisher.initialize()
            await self._load_sources()

            if not self.scrapers:
                logger.error("❌ Нет активных источников!")
                raise RuntimeError("No active sources configured")

            logger.info(f"✅ Готов. Источников: {len(self.scrapers)}")
            logger.info(
                f"⏰ Режим: посты новее {self.start_time.strftime('%H:%M:%S UTC')}"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            raise

    async def _load_sources(self) -> None:
        config_path = settings.sources_config

        if not config_path.exists():
            logger.warning(f"⚠️ Конфиг не найден: {config_path}")
            self._create_example_config(config_path)
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            sources_data = config.get("sources", [])
            enabled_count = 0

            for source_data in sources_data:
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
                    enabled_count += 1
                    logger.info(f"   {source}")
                except ValueError as e:
                    logger.error(f"❌ {source.url}: {e}")

            if enabled_count > 0:
                logger.info(f"📊 Загружено источников: {enabled_count}")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфига: {e}")

    def _create_example_config(self, path: Path) -> None:
        example_config = {
            "sources": [
                {"type": "telegram", "url": "https://t.me/example", "enabled": False},
                {"type": "vk", "url": "https://vk.com/public123", "enabled": False},
            ]
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(example_config, f, allow_unicode=True, sort_keys=False)
        logger.info(f"📝 Создан пример: {path}")

    async def run(self) -> None:
        if not self.scrapers:
            return

        self.running = True
        logger.info("🔄 Запуск цикла...")
        cycle_num = 0

        try:
            while self.running:
                cycle_num += 1
                logger.info(f"\n{'=' * 50}")
                logger.info(f"🔄 Цикл #{cycle_num}")
                logger.info(f"{'=' * 50}")

                try:
                    await self._scrape_and_publish_cycle()
                    self.cycle_errors = 0

                except Exception as e:
                    self.cycle_errors += 1
                    logger.error(f"❌ Ошибка цикла #{cycle_num}: {e}")

                    if self.cycle_errors >= self.max_consecutive_errors:
                        logger.error(
                            f"💥 Превышен лимит ошибок ({self.max_consecutive_errors}). "
                            "Остановка бота."
                        )
                        break

                    logger.warning(
                        f"⚠️ Ошибка {self.cycle_errors}/{self.max_consecutive_errors}. "
                        "Продолжаем работу..."
                    )

                logger.info(f"⏸️ Ожидание {settings.scrape_interval_seconds}s...\n")
                await asyncio.sleep(settings.scrape_interval_seconds)

        except KeyboardInterrupt:
            logger.info("\n⚠️ Остановка (Ctrl+C)")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
        finally:
            await self.shutdown()

    async def _scrape_and_publish_cycle(self) -> None:
        logger.info("📡 Сбор данных...")

        scrape_tasks = [
            scraper.scrape(limit=10, since_time=self.start_time)
            for scraper in self.scrapers
        ]
        results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

        all_posts: list[Post] = []
        errors = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Источник #{i + 1}: {result}")
                errors += 1
            elif isinstance(result, list):
                all_posts.extend(result)

        if errors > 0:
            logger.warning(f"⚠️ Ошибок при сборе: {errors}")

        if not all_posts:
            logger.info("ℹ️ Новых постов нет")
            return

        logger.info(f"📊 Собрано: {len(all_posts)}")

        new_count = 0
        published_count = 0
        skipped_old = 0
        skipped_dup = 0

        for post in all_posts:
            try:
                if await self.repository.is_post_processed(post.content_hash):
                    skipped_dup += 1
                    continue

                await self.repository.mark_post_processed(post)
                new_count += 1

                post_date = post.created_at
                if post_date.tzinfo is None:
                    post_date = post_date.replace(tzinfo=timezone.utc)

                if post_date < self.start_time:
                    skipped_old += 1
                    continue

                logger.info(f"🆕 {post.url}")
                logger.debug(f"   ⏳ Ожидание {settings.post_check_delay_seconds}s...")

                await asyncio.sleep(settings.post_check_delay_seconds)

                try:
                    msg_id = await self.publisher.publish_post(post)
                    await self.repository.mark_post_published(post.content_hash, msg_id)
                    published_count += 1
                    logger.info(f"✅ Опубликовано (msg_id: {msg_id})")

                except Exception as e:
                    await self.repository.mark_post_failed(post.content_hash, str(e))
                    logger.error(f"❌ Публикация провалена: {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка обработки поста: {e}")

        logger.info("\n📈 Итог:")
        logger.info(f"   Новых: {new_count}")
        logger.info(f"   Опубликовано: {published_count}")
        logger.info(f"   Пропущено (старые): {skipped_old}")
        logger.info(f"   Пропущено (дубли): {skipped_dup}")

    async def shutdown(self) -> None:
        logger.info("🛑 Завершение...")

        for scraper in self.scrapers:
            try:
                await scraper.close()
            except Exception as e:
                logger.debug(f"⚠️ Ошибка закрытия скрапера: {e}")

        try:
            await self.publisher.close()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка закрытия публикатора: {e}")

        try:
            await self.repository.close()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка закрытия БД: {e}")

        logger.info("👋 Остановлен")
