# app/scrapers/factory.py

"""Фабрика для создания скраперов."""

from app.models.content import PlatformType
from app.scrapers.base import BaseScraper
from app.scrapers.telegram import TelegramScraper
from app.scrapers.vk import VKScraper
from app.utils.logger import logger
from app.utils.validators import validate_telegram_url, validate_vk_url


class ScraperFactory:
    """Фабрика для создания скраперов по типу платформы."""

    @staticmethod
    def create_scraper(platform: str, source_url: str) -> BaseScraper:
        """Создает скрапер для указанной платформы.

        Args:
            platform: Тип платформы (telegram, vk)
            source_url: URL источника

        Returns:
            Экземпляр скрапера

        Raises:
            ValueError: Если платформа не поддерживается или URL невалиден
        """
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
        """Автоматически определяет платформу по URL.

        Args:
            source_url: URL источника

        Returns:
            Тип платформы или None
        """
        if validate_telegram_url(source_url):
            return PlatformType.TELEGRAM.value

        if validate_vk_url(source_url):
            return PlatformType.VK.value

        return None
