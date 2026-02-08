# Документация проекта

- **Источник:** `/home/pavel/projects/content-aggregator-bot`
- **Дата:** Sun Feb  8 03:15:51 MSK 2026
- **Файлов:** 21

## Структура проекта

```text
.
├── app
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── database
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── repository.py
│   ├── models
│   │   ├── __init__.py
│   │   └── content.py
│   ├── orchestrator.py
│   ├── publishers
│   │   ├── __init__.py
│   │   └── telegram.py
│   ├── scrapers
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── telegram.py
│   │   └── vk.py
│   └── utils
│       ├── __init__.py
│       ├── logger.py
│       ├── rate_limiter.py
│       └── validators.py
└── pyproject.toml
```

---

## Содержимое файлов

### app/__init__.py

```python
# app/__init__.py

__version__ = "0.1.0"
__author__ = "FH IT"
__description__ = (
    "Бот для автоматического мониторинга и репоста контента из Telegram и VK"
)

```

### app/__main__.py

```python
# app/__main__.py

import asyncio

from app.orchestrator import Orchestrator
from app.utils.logger import logger, setup_logger


async def main() -> None:
    setup_logger()

    logger.info("=" * 60)
    logger.info("Запуск Content Aggregator Bot")
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
        logger.info("Приложение завершено")


def run_main():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run_main()

```

### app/config.py

```python
# app/config.py

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: str = Field(..., description="Токен Telegram бота")
    telegram_target_chat_id: str = Field(
        ..., description="ID целевого чата для публикации"
    )

    telegram_api_id: int = Field(..., description="API ID из my.telegram.org")
    telegram_api_hash: str = Field(..., description="API Hash из my.telegram.org")
    telegram_session_name: str = Field(
        default="aggregator_session", description="Имя файла сессии Telegram"
    )

    vk_access_token: str = Field(..., description="Токен доступа VK API")
    vk_api_version: str = Field(default="5.131", description="Версия VK API")

    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/aggregator.db",
        description="URL подключения к базе данных",
    )

    log_level: str = Field(default="INFO", description="Уровень логирования")
    log_file: str = Field(default="logs/bot.log", description="Путь к файлу логов")

    scrape_interval_seconds: int = Field(
        default=60, description="Интервал между проверками источников (секунды)"
    )
    rate_limit_requests_per_minute: int = Field(
        default=30, description="Максимум запросов в минуту к API"
    )
    post_check_delay_seconds: int = Field(
        default=600, description="Задержка перед повторной проверкой поста (секунды)"
    )

    sources_config: Path = Field(
        default=Path("config/sources.yaml"),
        description="Путь к файлу со списком источников",
    )

    def ensure_directories(self) -> None:
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if self.database_url.startswith("sqlite"):
            db_path = self.database_url.split("///")[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.sources_config.parent.mkdir(parents=True, exist_ok=True)


# Отсутствуют аргументы для параметров "telegram_bot_token", "telegram_target_chat_id", "telegram_api_id", "telegram_api_hash", "vk_access_token"
settings = Settings()

```

### app/database/__init__.py

```python
# app/database/__init__.py

from app.database.models import Base, ProcessedPost
from app.database.repository import PostRepository

__all__ = ["Base", "ProcessedPost", "PostRepository"]

```

### app/database/models.py

```python
# app/database/models.py

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProcessedPost(Base):
    __tablename__ = "processed_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    url: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    target_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        """Строковое представление для отладки."""
        return (
            f"<ProcessedPost(id={self.id}, "
            f"platform={self.platform}, "
            f"post_id={self.post_id}, "
            f"published={self.published})>"
        )

```

### app/database/repository.py

```python
# app/database/repository.py

"""Слой доступа к данным (Repository Pattern)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base, ProcessedPost
from app.models.content import Post
from app.utils.logger import logger


class PostRepository:
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.debug(f"Репозиторий инициализирован: {database_url}")

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных инициализирована")

    async def is_post_processed(self, content_hash: str) -> bool:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            return result.scalar_one_or_none() is not None

    async def mark_post_processed(self, post: Post) -> ProcessedPost:
        async with self.session_factory() as session:
            db_post = ProcessedPost(
                platform=post.platform.value,
                source_id=post.source_id,
                post_id=post.post_id,
                content_hash=post.content_hash,
                url=post.url,
                created_at=post.created_at,
                processed_at=datetime.now(),
                published=False,
            )
            session.add(db_post)
            await session.commit()
            await session.refresh(db_post)

            logger.debug(
                f"Пост помечен как обработанный: {post.platform}:{post.post_id}"
            )
            return db_post

    async def mark_post_published(
        self, content_hash: str, target_message_id: int | None = None
    ) -> None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            db_post = result.scalar_one_or_none()

            if db_post:
                db_post.published = True
                db_post.published_at = datetime.now()
                db_post.target_message_id = target_message_id
                await session.commit()
                logger.debug(f"Пост помечен как опубликованный: {content_hash[:16]}...")

    async def mark_post_failed(self, content_hash: str, error_message: str) -> None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            db_post = result.scalar_one_or_none()

            if db_post:
                db_post.published = False
                db_post.error_message = error_message
                await session.commit()
                logger.warning(
                    f"Пост помечен как проваленный: {content_hash[:16]}... - {error_message}"
                )

    async def get_post_by_hash(self, content_hash: str) -> ProcessedPost | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            return result.scalar_one_or_none()

    async def get_unpublished_posts(self, limit: int = 100) -> list[ProcessedPost]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost)
                # Avoid equality comparisons to `False`; use `not ProcessedPost.published:` for false checks
                .where(ProcessedPost.published == False)
                .where(ProcessedPost.error_message.is_(None))
                .order_by(ProcessedPost.created_at)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def close(self) -> None:
        await self.engine.dispose()
        logger.debug("Соединение с БД закрыто")

```

### app/models/__init__.py

```python
# app/models/__init__.py

from app.models.content import Media, MediaType, PlatformType, Post, PublishedPost

__all__ = ["Media", "MediaType", "PlatformType", "Post", "PublishedPost"]

```

### app/models/content.py

```python
# app/models/content.py

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PlatformType(str, Enum):
    TELEGRAM = "telegram"
    VK = "vk"


class MediaType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"


class Media(BaseModel):
    type: MediaType
    url: str | None = None
    file_id: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    mime_type: str | None = None


class Post(BaseModel):
    platform: PlatformType
    source_id: str = Field(..., description="ID источника (канал, группа)")
    post_id: str = Field(..., description="Уникальный ID поста на платформе")

    text: str | None = None
    media: list[Media] = Field(default_factory=list)
    url: str = Field(..., description="Ссылка на оригинальный пост")

    author: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    views: int | None = None

    content_hash: str = Field(..., description="Хеш контента для дедупликации")

    class Config:
        use_enum_values = True

    def __str__(self) -> str:
        preview = (
            (self.text[:50] + "...") if self.text and len(self.text) > 50 else self.text
        )
        return f"Post({self.platform}:{self.post_id}, text={preview})"

    def __repr__(self) -> str:
        return self.__str__()


class PublishedPost(BaseModel):
    original_post: Post
    published_at: datetime = Field(default_factory=datetime.now)
    target_message_id: int | None = None
    success: bool = True
    error_message: str | None = None

```

### app/orchestrator.py

```python
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
            if await self.repository.is_post_processed(post.content_hash):
                continue

            await self.repository.mark_post_processed(post)
            new_count += 1

            post_date = post.created_at
            if post_date.tzinfo is None:
                post_date = post_date.replace(tzinfo=timezone.utc)

            if post_date < self.start_time:
                logger.debug(f"Пропущен старый пост: {post.url} ({post_date})")
                skipped_old_count += 1
                continue

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

```

### app/publishers/__init__.py

```python
# app/publishers/__init__.py

from app.publishers.telegram import TelegramPublisher

__all__ = ["TelegramPublisher"]

```

### app/publishers/telegram.py

```python
# app/publishers/telegram.py

import os
import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.types import InputMediaPhoto, InputMediaVideo, FSInputFile
from aiogram.exceptions import TelegramRetryAfter
from app.config import settings
from app.models.content import Post, MediaType
from app.utils.logger import logger


class TelegramPublisher:
    def __init__(self):
        self.bot: Bot | None = None
        self.target_chat_id = settings.telegram_target_chat_id

    async def initialize(self) -> None:
        self.bot = Bot(token=settings.telegram_bot_token)
        logger.info("Публикатор готов")

    def _get_input_file(self, media_url: str):
        if os.path.exists(media_url):
            return FSInputFile(media_url)
        return media_url

    def _prepare_caption(self, post: Post) -> str:
        text = post.text or ""
        date_str = post.created_at.strftime("%d.%m.%Y %H:%M")
        footer = f"\n\n📅 {date_str}\n🔗 {post.url}"
        max_text_len = 1024 - len(footer) - 5

        if len(text) > max_text_len:
            text = text[:max_text_len] + "..."

        return text + footer

    async def publish_post(self, post: Post) -> int | None:
        if not self.bot:
            raise RuntimeError("Публикатор не инициализирован")

        try:
            final_caption = self._prepare_caption(post)

            if not post.media:
                msg = await self.bot.send_message(
                    self.target_chat_id,
                    text=final_caption,
                    disable_web_page_preview=True,  # Чтобы не было превью ссылки-источника
                )
                return msg.message_id

            if len(post.media) == 1:
                m = post.media[0]
                # Аргумент типа "str | None" нельзя присвоить параметру "media_url" типа "str" в функции "_get_input_file"
                #   "str | None" типа невозможно назначить тип "str"
                #       "None" невозможно назначить "str"
                file = self._get_input_file(m.url)

                if m.type == MediaType.PHOTO:
                    msg = await self.bot.send_photo(
                        self.target_chat_id, photo=file, caption=final_caption
                    )
                elif m.type == MediaType.VIDEO:
                    msg = await self.bot.send_video(
                        self.target_chat_id, video=file, caption=final_caption
                    )
                else:
                    msg = await self.bot.send_document(
                        self.target_chat_id, document=file, caption=final_caption
                    )
                return msg.message_id

            else:
                media_group = []
                for i, m in enumerate(post.media[:10]):
                    # Аргумент типа "str | None" нельзя присвоить параметру "media_url" типа "str" в функции "_get_input_file"
                    #   "str | None" типа невозможно назначить тип "str"
                    #       "None" невозможно назначить "str"
                    file = self._get_input_file(m.url)
                    cap = final_caption if i == 0 else None

                    if m.type == MediaType.PHOTO:
                        media_group.append(InputMediaPhoto(media=file, caption=cap))
                    elif m.type == MediaType.VIDEO:
                        media_group.append(InputMediaVideo(media=file, caption=cap))

                msgs = await self.bot.send_media_group(
                    self.target_chat_id, media=media_group
                )
                return msgs[0].message_id

        except TelegramRetryAfter as e:
            logger.warning(f"Flood limit. Ждем {e.retry_after}с")
            await asyncio.sleep(e.retry_after)
            return await self.publish_post(post)
        except Exception as e:
            logger.error(f"Ошибка публикации: {e}")
            raise

    async def close(self) -> None:
        if self.bot:
            await self.bot.session.close()

```

### app/scrapers/__init__.py

```python
# app/scrapers/__init__.py

from app.scrapers.base import BaseScraper
from app.scrapers.factory import ScraperFactory
from app.scrapers.telegram import TelegramScraper
from app.scrapers.vk import VKScraper

__all__ = ["BaseScraper", "ScraperFactory", "TelegramScraper", "VKScraper"]

```

### app/scrapers/base.py

```python
# app/scrapers/base.py

from abc import ABC, abstractmethod
from datetime import datetime
from app.models.content import Post
from app.utils.logger import logger
from app.utils.rate_limiter import AdaptiveRateLimiter


class BaseScraper(ABC):
    def __init__(
        self, source_url: str, rate_limiter: AdaptiveRateLimiter | None = None
    ):
        self.source_url = source_url
        self.rate_limiter = rate_limiter or AdaptiveRateLimiter(
            max_requests=30, time_window=60
        )
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def fetch_recent_posts(
        self, limit: int = 10, since_time: datetime | None = None
    ) -> list[Post]:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    async def scrape(
        self, limit: int = 10, since_time: datetime | None = None
    ) -> list[Post]:
        try:
            if not self._initialized:
                await self.initialize()
                self._initialized = True

            posts = await self.fetch_recent_posts(limit, since_time)
            await self.rate_limiter.reset_errors()
            return posts

        except Exception as e:
            logger.error(f"Ошибка при сборе данных из {self.source_url}: {e}")
            await self.rate_limiter.handle_error(e)
            return []

```

### app/scrapers/factory.py

```python
# app/scrapers/factory.py

from app.models.content import PlatformType
from app.scrapers.base import BaseScraper
from app.scrapers.telegram import TelegramScraper
from app.scrapers.vk import VKScraper
from app.utils.logger import logger
from app.utils.validators import validate_telegram_url, validate_vk_url


class ScraperFactory:
    @staticmethod
    def create_scraper(platform: str, source_url: str) -> BaseScraper:
        platform = platform.lower()

        if platform == PlatformType.TELEGRAM.value:
            if not validate_telegram_url(source_url):
                raise ValueError(f"Невалидный Telegram URL: {source_url}")
            logger.debug(f"Создан Telegram скрапер для {source_url}")
            return TelegramScraper(source_url)

        elif platform == PlatformType.VK.value:
            if not validate_vk_url(source_url):
                raise ValueError(f"Невалидный VK URL: {source_url}")
            logger.debug(f"Создан VK скрапер для {source_url}")
            return VKScraper(source_url)

        else:
            raise ValueError(
                f"Неподдерживаемая платформа: {platform}. "
                f"Доступные: {[p.value for p in PlatformType]}"
            )

    @staticmethod
    def auto_detect_platform(source_url: str) -> str | None:
        if validate_telegram_url(source_url):
            return PlatformType.TELEGRAM.value

        if validate_vk_url(source_url):
            return PlatformType.VK.value

        return None

```

### app/scrapers/telegram.py

```python
# app/scrapers/telegram.py

import os
import asyncio
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.tl.types import Message, MessageMediaPhoto
from app.config import settings
from app.models.content import Media, MediaType, PlatformType, Post
from app.scrapers.base import BaseScraper
from app.utils.logger import logger
from app.utils.validators import (
    extract_telegram_username,
    generate_content_hash,
    sanitize_text,
)

_init_lock = asyncio.Lock()


class TelegramScraper(BaseScraper):
    _shared_client: TelegramClient | None = None

    def __init__(self, source_url: str):
        super().__init__(source_url)
        self.username = extract_telegram_username(source_url)
        self.temp_dir = "data/temp"
        os.makedirs(self.temp_dir, exist_ok=True)

    async def initialize(self) -> None:
        async with _init_lock:
            if TelegramScraper._shared_client is None:
                client = TelegramClient(
                    settings.telegram_session_name,
                    settings.telegram_api_id,
                    settings.telegram_api_hash,
                    # Аргумент типа "None" нельзя присвоить параметру "connection_retries" типа "int" в функции "__init__"
                    #   "None" невозможно назначить "int"
                    connection_retries=None,
                )
                # "TelegramClient" не является awaitable
                #   "TelegramClient" несовместим с протоколом "Awaitable[_T_co@Awaitable]"
                #       "__await__" отсутствует.
                await client.start()
                TelegramScraper._shared_client = client
                logger.success("Общий Telegram клиент запущен")
            self.client = TelegramScraper._shared_client

    async def _ensure_connected(self):
        if not self.client:
            await self.initialize()
        if not self.client.is_connected():
            try:
                await self.client.connect()
            except Exception:
                pass

    async def fetch_recent_posts(
        self, limit: int = 10, since_time: datetime | None = None
    ) -> list[Post]:
        await self._ensure_connected()
        posts = []
        try:
            # Аргумент типа "str | None" нельзя присвоить параметру "entity" типа "EntitiesLike" в функции "get_entity"
            #   "str | None" типа невозможно назначить тип "EntitiesLike"
            #       "None" типа невозможно назначить тип "EntitiesLike"
            #       "None" невозможно назначить "str"
            #       "None" невозможно назначить "int"
            #       "None" невозможно назначить "PeerUser"
            #       "None" невозможно назначить "PeerChat"
            #       "None" невозможно назначить "PeerChannel"
            #       "None" невозможно назначить "InputPeerEmpty"
            #   ...
            entity = await self.client.get_entity(self.username)
            # Аргумент типа "Entity | List[Entity]" нельзя присвоить параметру "entity" типа "EntityLike" в функции "iter_messages"
            #   "Entity | List[Entity]" типа невозможно назначить тип "EntityLike"
            #       "List[Entity]" типа невозможно назначить тип "EntityLike"
            #       "List[Entity]" невозможно назначить "str"
            #       "List[Entity]" невозможно назначить "int"
            #       "List[Entity]" невозможно назначить "PeerUser"
            #       "List[Entity]" невозможно назначить "PeerChat"
            #       "List[Entity]" невозможно назначить "PeerChannel"
            #       "List[Entity]" невозможно назначить "InputPeerEmpty"
            #   ...
            async for message in self.client.iter_messages(entity, limit=limit):
                if not isinstance(message, Message):
                    continue

                # === ОПТИМИЗАЦИЯ ===
                # Если передан since_time, проверяем дату СРАЗУ
                if since_time:
                    msg_date = message.date
                    # "tzinfo" не является известным атрибутом "None"
                    if msg_date.tzinfo is None:
                        # "replace" не является известным атрибутом "None"
                        msg_date = msg_date.replace(tzinfo=timezone.utc)

                    # Оператор "<" не поддерживается для "None"
                    if msg_date < since_time:
                        break

                post = await self._parse_message(message)
                if post:
                    posts.append(post)

        except Exception as e:
            logger.error(f"Ошибка сбора {self.username}: {e}")
        return posts

    async def _parse_message(self, message: Message) -> Post | None:
        try:
            text = sanitize_text(message.message)
            media_list = []

            if message.media:
                try:
                    file_path = await asyncio.wait_for(
                        # Не удается получить доступ к атрибуту "download_media" для класса "Message"
                        #   Атрибут "download_media" неизвестен
                        message.download_media(file=self.temp_dir + "/"),
                        timeout=30.0,
                    )
                    if file_path:
                        m_type = MediaType.DOCUMENT
                        if isinstance(message.media, MessageMediaPhoto):
                            m_type = MediaType.PHOTO
                        elif (
                            hasattr(message.media, "document")
                            # Не удается получить доступ к атрибуту "document" для класса "MessageMedia*"
                            #   Атрибут "document" неизвестен
                            and message.media.document
                            # Не удается получить доступ к атрибуту "document" для класса "MessageMedia*"
                            #   Атрибут "document" неизвестен
                            # Не удается получить доступ к атрибуту "mime_type" для класса "DocumentEmpty"
                            #   Атрибут "mime_type" неизвестен
                            and message.media.document.mime_type.startswith("video")
                        ):
                            m_type = MediaType.VIDEO

                        media_list.append(
                            Media(type=m_type, url=os.path.abspath(file_path))
                        )
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

            if not text and not media_list:
                return None

            content_hash = generate_content_hash(text, [m.url for m in media_list])
            return Post(
                platform=PlatformType.TELEGRAM,
                # Аргумент типа "str | None" нельзя присвоить параметру "source_id" типа "str" в функции "__init__"
                #   "str | None" типа невозможно назначить тип "str"
                #       "None" невозможно назначить "str"
                source_id=self.username,
                post_id=str(message.id),
                text=text,
                media=media_list,
                url=f"https://t.me/{self.username}/{message.id}",
                # Аргумент типа "datetime | None" нельзя присвоить параметру "created_at" типа "datetime" в функции "__init__"
                #   "datetime | None" типа невозможно назначить тип "datetime"
                #       "None" невозможно назначить "datetime"
                created_at=message.date,
                content_hash=content_hash,
            )
        except Exception:
            return None

    async def close(self):
        pass

```

### app/scrapers/vk.py

```python
# app/scrapers/vk.py

from datetime import datetime, timezone
import vk_api
from app.config import settings
from app.models.content import Media, MediaType, PlatformType, Post
from app.scrapers.base import BaseScraper
from app.utils.logger import logger
from app.utils.validators import extract_vk_id, generate_content_hash, sanitize_text


class VKScraper(BaseScraper):
    def __init__(self, source_url: str):
        super().__init__(source_url)
        self.group_id = extract_vk_id(source_url)
        self.vk_session = None
        self.vk = None

    async def initialize(self) -> None:
        try:
            self.vk_session = vk_api.VkApi(token=settings.vk_access_token)
            self.vk = self.vk_session.get_api()
            logger.info(f"VK API инициализирован для {self.group_id}")
        except Exception as e:
            logger.error(f"Ошибка VK API: {e}")

    async def fetch_recent_posts(
        self, limit: int = 10, since_time: datetime | None = None
    ) -> list[Post]:
        if not self.vk:
            await self.initialize()
        posts = []
        try:
            # "wall" не является известным атрибутом "None"
            response = self.vk.wall.get(
                domain=self.group_id,
                count=limit,
                filter="owner",
                v=settings.vk_api_version,
            )
            items = response.get("items", [])

            for item in items:
                if since_time:
                    timestamp = item.get("date", 0)
                    post_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    if post_date < since_time:
                        continue

                post = self._parse_post(item)
                if post:
                    posts.append(post)

        except Exception as e:
            logger.error(f"Ошибка сбора VK {self.group_id}: {e}")
        return posts

    def _parse_post(self, item: dict) -> Post | None:
        try:
            post_id = str(item.get("id"))
            owner_id = item.get("owner_id")
            text = sanitize_text(item.get("text"))
            media_list = []
            for attachment in item.get("attachments", []):
                att_type = attachment.get("type")
                if att_type == "photo":
                    sizes = attachment.get("photo", {}).get("sizes", [])
                    if sizes:
                        largest = max(sizes, key=lambda x: x.get("width", 0))
                        media_list.append(
                            Media(type=MediaType.PHOTO, url=largest.get("url"))
                        )
                elif att_type == "video":  # Видео в VK сложное, нужна ссылка на плеер
                    # Упрощенная логика для примера
                    pass

            if not text and not media_list:
                return None

            timestamp = item.get("date", 0)
            created_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)

            url = f"https://vk.com/wall{owner_id}_{post_id}"
            content_hash = generate_content_hash(
                text, [m.url for m in media_list if m.url]
            )

            return Post(
                platform=PlatformType.VK,
                # Аргумент типа "str | None" нельзя присвоить параметру "source_id" типа "str" в функции "__init__"
                #   "str | None" типа невозможно назначить тип "str"
                #       "None" невозможно назначить "str"
                source_id=self.group_id,
                post_id=post_id,
                text=text,
                media=media_list,
                url=url,
                created_at=created_at,
                content_hash=content_hash,
            )
        # Do not use bare `except`
        except:
            return None

    async def close(self) -> None:
        pass

```

### app/utils/__init__.py

```python
# app/utils/__init__.py

from app.utils.logger import logger, setup_logger
from app.utils.rate_limiter import AdaptiveRateLimiter, RateLimiter
from app.utils.validators import (
    extract_telegram_username,
    extract_vk_id,
    generate_content_hash,
    sanitize_text,
    validate_telegram_url,
    validate_vk_url,
)

__all__ = [
    "logger",
    "setup_logger",
    "RateLimiter",
    "AdaptiveRateLimiter",
    "validate_telegram_url",
    "validate_vk_url",
    "extract_telegram_username",
    "extract_vk_id",
    "generate_content_hash",
    "sanitize_text",
]

```

### app/utils/logger.py

```python
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

```

### app/utils/rate_limiter.py

```python
# app/utils/rate_limiter.py

import asyncio
import time
from collections import deque
from functools import wraps

from app.utils.logger import logger


class RateLimiter:
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.time()

            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()

            if len(self.requests) >= self.max_requests:
                sleep_time = self.time_window - (now - self.requests[0])
                if sleep_time > 0:
                    logger.debug(f"Rate limit достигнут. Ожидание {sleep_time:.1f}s")
                    await asyncio.sleep(sleep_time)
                    await self.acquire()
                    return

            self.requests.append(now)

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await self.acquire()
            return await func(*args, **kwargs)

        return wrapper


class AdaptiveRateLimiter(RateLimiter):
    def __init__(
        self,
        max_requests: int,
        time_window: int = 60,
        max_retries: int = 5,
        base_delay: float = 1.0,
    ):
        super().__init__(max_requests, time_window)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.consecutive_errors = 0

    async def handle_error(self, error: Exception) -> None:
        self.consecutive_errors += 1

        if self.consecutive_errors > self.max_retries:
            logger.error(
                f"Превышено количество попыток ({self.max_retries}). "
                f"Последняя ошибка: {error}"
            )
            raise

        delay = self.base_delay * (2 ** (self.consecutive_errors - 1))
        logger.warning(
            f"Ошибка #{self.consecutive_errors}: {error}. Повтор через {delay:.1f}s"
        )
        await asyncio.sleep(delay)

    async def reset_errors(self) -> None:
        if self.consecutive_errors > 0:
            logger.debug("Счетчик ошибок сброшен после успешного запроса")
            self.consecutive_errors = 0

```

### app/utils/validators.py

```python
# app/utils/validators.py

import hashlib
import re


def validate_telegram_url(url: str) -> bool:
    pattern = r"^https?://t\.me/[a-zA-Z0-9_]+/?$"
    return bool(re.match(pattern, url))


def validate_vk_url(url: str) -> bool:
    pattern = r"^https?://vk\.com/(public|club|)[a-zA-Z0-9_]+/?$"
    return bool(re.match(pattern, url))


def extract_telegram_username(url: str) -> str | None:
    match = re.search(r"t\.me/([a-zA-Z0-9_]+)", url)
    return match.group(1) if match else None


def extract_vk_id(url: str) -> str | None:
    match = re.search(r"vk\.com/(public|club|)([a-zA-Z0-9_]+)", url)
    return match.group(2) if match else None


def generate_content_hash(text: str | None, media_urls: list[str] | None = None) -> str:
    content = ""

    if text:
        normalized_text = " ".join(text.split())
        content += normalized_text

    if media_urls:
        content += "|".join(sorted(media_urls))

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sanitize_text(text: str | None) -> str | None:
    if not text:
        return None

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text if text else None

```

### pyproject.toml

```toml
[project]
name = "content-aggregator-bot"
version = "0.1.0"
description = "soon..."
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "aiogram",
    "aiohttp",
    "aiosqlite",
    "loguru",
    "pydantic",
    "pydantic-settings",
    "python-dotenv",
    "pyyaml",
    "sqlalchemy",
    "telethon",
    "vk-api",
]

[dependency-groups]
dev = ["ruff"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]

[project.scripts]
bot = "app.__main__:run_main"

```

