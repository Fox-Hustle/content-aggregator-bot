# app/database/__init__.py

"""Модуль работы с базой данных."""

from app.database.models import Base, ProcessedPost
from app.database.repository import PostRepository

__all__ = ["Base", "ProcessedPost", "PostRepository"]
