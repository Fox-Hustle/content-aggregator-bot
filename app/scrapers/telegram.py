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
