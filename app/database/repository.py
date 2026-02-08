# app/database/repository.py

"""Слой доступа к данным (Repository Pattern)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base, ProcessedPost
from app.models.content import Post
from app.utils.logger import logger


class PostRepository:
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.debug(f"Репозиторий инициализирован: {database_url}")

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных инициализирована")

    async def is_post_processed(self, content_hash: str) -> bool:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            return result.scalar_one_or_none() is not None

    async def mark_post_processed(self, post: Post) -> ProcessedPost:
        async with self.session_factory() as session:
            db_post = ProcessedPost(
                platform=post.platform.value,
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
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost).where(ProcessedPost.content_hash == content_hash)
            )
            return result.scalar_one_or_none()

    async def get_unpublished_posts(self, limit: int = 100) -> list[ProcessedPost]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProcessedPost)
                # Avoid equality comparisons to `False`; use `not ProcessedPost.published:` for false checks
                .where(ProcessedPost.published == False)
                .where(ProcessedPost.error_message.is_(None))
                .order_by(ProcessedPost.created_at)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def close(self) -> None:
        await self.engine.dispose()
        logger.debug("Соединение с БД закрыто")
