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
