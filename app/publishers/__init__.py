# app/publishers/__init__.py

"""Модуль публикаторов контента."""

from app.publishers.telegram import TelegramPublisher

__all__ = ["TelegramPublisher"]
