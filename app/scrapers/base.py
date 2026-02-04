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
    # Добавляем аргумент since_time
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

            # Передаем since_time внутрь
            posts = await self.fetch_recent_posts(limit, since_time)
            await self.rate_limiter.reset_errors()
            return posts

        except Exception as e:
            logger.error(f"Ошибка при сборе данных из {self.source_url}: {e}")
            await self.rate_limiter.handle_error(e)
            return []
