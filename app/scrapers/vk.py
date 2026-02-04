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
            response = self.vk.wall.get(
                domain=self.group_id,
                count=limit,
                filter="owner",
                v=settings.vk_api_version,
            )
            items = response.get("items", [])

            for item in items:
                # === ОПТИМИЗАЦИЯ ===
                if since_time:
                    timestamp = item.get("date", 0)
                    post_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    if post_date < since_time:
                        continue  # Или break, если уверены в сортировке VK
                # ===================

                post = self._parse_post(item)
                if post:
                    posts.append(post)

        except Exception as e:
            logger.error(f"Ошибка сбора VK {self.group_id}: {e}")
        return posts

    def _parse_post(self, item: dict) -> Post | None:
        # (Код парсинга остается без изменений, скопируйте его из предыдущей версии или исходника)
        # Для краткости я его здесь не дублирую, так как меняем только fetch_recent_posts
        try:
            # ... (старый код парсинга)
            # Вставьте сюда содержимое метода _parse_post из вашего текущего файла
            # Если нужно - я могу прислать полный код файла
            pass
        except:
            return None
        # ВРЕМЕННАЯ ЗАГЛУШКА ДЛЯ ПРИМЕРА - НЕ КОПИРУЙТЕ МЕТОД _parse_post ПУСТЫМ!
        # Используйте старый _parse_post.

        # --- ВОССТАНОВЛЕНИЕ _parse_post (на всякий случай) ---
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
                source_id=self.group_id,
                post_id=post_id,
                text=text,
                media=media_list,
                url=url,
                created_at=created_at,
                content_hash=content_hash,
            )
        except:
            return None

    async def close(self) -> None:
        pass
