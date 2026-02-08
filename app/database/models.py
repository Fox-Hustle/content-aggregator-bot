# app/database/models.py

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProcessedPost(Base):
    __tablename__ = "processed_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    url: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    target_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        """Строковое представление для отладки."""
        return (
            f"<ProcessedPost(id={self.id}, "
            f"platform={self.platform}, "
            f"post_id={self.post_id}, "
            f"published={self.published})>"
        )
