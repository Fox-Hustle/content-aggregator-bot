# app/database/repository.py

"""Слой доступа к данным (Repository Pattern)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base, ProcessedPost
from app.models.content import Post
from app.utils.logger import logger


class PostRepository:
    """Репозиторий для работы с постами."""

    def __init__(self, database_url: str):
        """Инициализация репозитория.

        Args:
            database_url: URL подключения к базе данных
        """
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.debug(f"Репозиторий инициализирован: {database_url}")

    async def init_db(self) -> None:
        """Создает таблицы в базе данных."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных инициализирована")

    async def is_post_processed(self, content_hash: str) -> bool:
        """Проверяет, был ли пост уже обработан.

        Args:
            content_hash: Хеш контента поста

        Returns:
            True если пост уже обрабатывался
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            return result.scalar_one_or_none() is not None

    async def mark_post_processed(self, post: Post) -> ProcessedPost:
        """Отмечает пост как обработанный.

        Args:
            post: Объект поста для сохранения

        Returns:
            Сохраненная запись в БД
        """
        async with self.session_factory() as session:
            db_post = ProcessedPost(
                platform=post.platform,
                source_id=post.source_id,
                post_id=post.post_id,
                content_hash=post.content_hash,
                url=post.url,
                created_at=post.created_at,
                processed_at=datetime.now(),
                published=False,
            )
            session.add(db_post)
            await session.commit()
            await session.refresh(db_post)

            logger.debug(
                f"Пост помечен как обработанный: {post.platform}:{post.post_id}"
            )
            return db_post

    async def mark_post_published(
        self, content_hash: str, target_message_id: int | None = None
    ) -> None:
        """Отмечает пост как опубликованный.

        Args:
            content_hash: Хеш контента поста
            target_message_id: ID сообщения в целевом чате
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            db_post = result.scalar_one_or_none()

            if db_post:
                db_post.published = True
                db_post.published_at = datetime.now()
                db_post.target_message_id = target_message_id
                await session.commit()
                logger.debug(f"Пост помечен как опубликованный: {content_hash[:16]}...")

    async def mark_post_failed(self, content_hash: str, error_message: str) -> None:
        """Отмечает пост как проваленный при публикации.

        Args:
            content_hash: Хеш контента поста
            error_message: Сообщение об ошибке
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            db_post = result.scalar_one_or_none()

            if db_post:
                db_post.published = False
                db_post.error_message = error_message
                await session.commit()
                logger.warning(
                    f"Пост помечен как проваленный: {content_hash[:16]}... - {error_message}"
                )

    async def get_post_by_hash(self, content_hash: str) -> ProcessedPost | None:
        """Получает пост по хешу контента.

        Args:
            content_hash: Хеш контента

        Returns:
            Объект ProcessedPost или None
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            return result.scalar_one_or_none()

    async def get_unpublished_posts(self, limit: int = 100) -> list[ProcessedPost]:
        """Получает неопубликованные посты.

        Args:
            limit: Максимальное количество постов

        Returns:
            Список неопубликованных постов
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost)
                .where(not ProcessedPost.published)
                .where(ProcessedPost.error_message.is_(None))
                .order_by(ProcessedPost.created_at)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def close(self) -> None:
        """Закрывает соединение с базой данных."""
        await self.engine.dispose()
        logger.debug("Соединение с БД закрыто")
