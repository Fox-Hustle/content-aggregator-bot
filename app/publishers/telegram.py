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
