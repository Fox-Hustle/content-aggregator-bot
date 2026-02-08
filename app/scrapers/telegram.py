# app/scrapers/telegram.py

import os
import asyncio
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument
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
        username = extract_telegram_username(source_url)
        if not username:
            raise ValueError(f"Невозможно извлечь username из {source_url}")
        self.username = username
        self.temp_dir = "data/temp"
        os.makedirs(self.temp_dir, exist_ok=True)

    async def initialize(self) -> None:
        async with _init_lock:
            if TelegramScraper._shared_client is None:
                client = TelegramClient(
                    settings.telegram_session_name,
                    settings.telegram_api_id,
                    settings.telegram_api_hash,
                )
                await client.start()
                TelegramScraper._shared_client = client
                logger.info("✅ Общий Telegram клиент запущен")
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
            entity = await self.client.get_entity(self.username)

            async for message in self.client.iter_messages(entity, limit=limit):
                if not isinstance(message, Message):
                    continue

                if since_time and message.date:
                    msg_date = message.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)
                    if msg_date < since_time:
                        break

                post = await self._parse_message(message)
                if post:
                    posts.append(post)

        except Exception as e:
            logger.error(f"❌ Ошибка сбора {self.username}: {e}")

        return posts

    async def _parse_message(self, message: Message) -> Post | None:
        try:
            text = sanitize_text(message.message)
            media_list = []

            if message.media:
                try:
                    file_path = await asyncio.wait_for(
                        message.download_media(file=self.temp_dir + "/"),
                        timeout=30.0,
                    )

                    if file_path:
                        m_type = MediaType.DOCUMENT

                        if isinstance(message.media, MessageMediaPhoto):
                            m_type = MediaType.PHOTO
                        elif isinstance(message.media, MessageMediaDocument):
                            doc = message.media.document
                            if doc and hasattr(doc, "mime_type") and doc.mime_type:
                                if doc.mime_type.startswith("video"):
                                    m_type = MediaType.VIDEO

                        media_list.append(
                            Media(type=m_type, url=os.path.abspath(file_path))
                        )
                except asyncio.TimeoutError:
                    logger.warning(f"⏱️ Таймаут скачивания медиа для поста {message.id}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка скачивания медиа: {e}")

            if not text and not media_list:
                return None

            # Проверка на None для message.date
            if not message.date:
                logger.warning(f"⚠️ Пост {message.id} не имеет даты, пропускаем")
                return None

            content_hash = generate_content_hash(
                text, [m.url for m in media_list if m.url]
            )

            return Post(
                platform=PlatformType.TELEGRAM,
                source_id=self.username,
                post_id=str(message.id),
                text=text,
                media=media_list,
                url=f"https://t.me/{self.username}/{message.id}",
                created_at=message.date,
                content_hash=content_hash,
            )
        except Exception as e:
            logger.debug(f"⚠️ Не удалось распарсить сообщение: {e}")
            return None

    async def close(self):
        pass
