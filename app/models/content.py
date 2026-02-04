# app/models/content.py

"""Модели данных для контента."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PlatformType(str, Enum):
    """Тип платформы-источника."""

    TELEGRAM = "telegram"
    VK = "vk"


class MediaType(str, Enum):
    """Тип медиафайла."""

    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"


class Media(BaseModel):
    """Модель медиафайла."""

    type: MediaType
    url: str | None = None
    file_id: str | None = None  # Для Telegram
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    mime_type: str | None = None


class Post(BaseModel):
    """Модель поста из любого источника."""

    # Идентификация
    platform: PlatformType
    source_id: str = Field(..., description="ID источника (канал, группа)")
    post_id: str = Field(..., description="Уникальный ID поста на платформе")

    # Контент
    text: str | None = None
    media: list[Media] = Field(default_factory=list)
    url: str = Field(..., description="Ссылка на оригинальный пост")

    # Метаданные
    author: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    views: int | None = None

    # Служебные поля
    content_hash: str = Field(..., description="Хеш контента для дедупликации")

    class Config:
        """Настройки модели."""

        use_enum_values = True

    def __str__(self) -> str:
        """Строковое представление поста."""
        preview = (
            (self.text[:50] + "...") if self.text and len(self.text) > 50 else self.text
        )
        return f"Post({self.platform}:{self.post_id}, text={preview})"

    def __repr__(self) -> str:
        """Представление для отладки."""
        return self.__str__()


class PublishedPost(BaseModel):
    """Модель опубликованного поста (для истории)."""

    original_post: Post
    published_at: datetime = Field(default_factory=datetime.now)
    target_message_id: int | None = None
    success: bool = True
    error_message: str | None = None
