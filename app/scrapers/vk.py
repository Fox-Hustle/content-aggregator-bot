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
        group_id = extract_vk_id(source_url)
        if not group_id:
            raise ValueError(f"Невозможно извлечь ID из {source_url}")
        self.group_id = group_id
        self.vk_session = None
        self.vk = None

    async def initialize(self) -> None:
        try:
            self.vk_session = vk_api.VkApi(token=settings.vk_access_token)
            self.vk = self.vk_session.get_api()
            logger.info(f"✅ VK API инициализирован для {self.group_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка VK API: {e}")
            raise

    async def fetch_recent_posts(
        self, limit: int = 10, since_time: datetime | None = None
    ) -> list[Post]:
        if not self.vk:
            await self.initialize()

        posts = []
        try:
            response = self.vk.wall.get(
                domain=self.group_id,
                count=min(limit, 100),
                filter="owner",
                v=settings.vk_api_version,
            )
            items = response.get("items", [])

            for item in items:
                if since_time:
                    timestamp = item.get("date", 0)
                    post_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    if post_date < since_time:
                        break

                post = self._parse_post(item)
                if post:
                    posts.append(post)

        except Exception as e:
            logger.error(f"❌ Ошибка сбора VK {self.group_id}: {e}")

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
                        url = largest.get("url")
                        if url:
                            media_list.append(
                                Media(
                                    type=MediaType.PHOTO,
                                    url=url,
                                    width=largest.get("width"),
                                    height=largest.get("height"),
                                )
                            )

                elif att_type == "video":
                    video = attachment.get("video", {})
                    video_id = video.get("id")
                    video_owner = video.get("owner_id")
                    if video_id and video_owner:
                        media_list.append(
                            Media(
                                type=MediaType.VIDEO,
                                url=f"https://vk.com/video{video_owner}_{video_id}",
                                width=video.get("width"),
                                height=video.get("height"),
                                duration=video.get("duration"),
                            )
                        )

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
        except Exception as e:
            logger.debug(f"⚠️ Не удалось распарсить VK пост: {e}")
            return None

    async def close(self) -> None:
        pass
