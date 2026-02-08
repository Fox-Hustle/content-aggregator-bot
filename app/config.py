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
