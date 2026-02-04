# app/scrapers/__init__.py

"""Модуль скраперов для различных платформ."""

from app.scrapers.base import BaseScraper
from app.scrapers.factory import ScraperFactory
from app.scrapers.telegram import TelegramScraper
from app.scrapers.vk import VKScraper

__all__ = ["BaseScraper", "ScraperFactory", "TelegramScraper", "VKScraper"]
