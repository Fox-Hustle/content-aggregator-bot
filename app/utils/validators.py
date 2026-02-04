# app/utils/validators.py

"""Валидаторы для проверки данных."""

import hashlib
import re


def validate_telegram_url(url: str) -> bool:
    """Проверяет, является ли URL валидным Telegram каналом/группой.

    Args:
        url: URL для проверки

    Returns:
        True если URL валиден
    """
    pattern = r"^https?://t\.me/[a-zA-Z0-9_]+/?$"
    return bool(re.match(pattern, url))


def validate_vk_url(url: str) -> bool:
    """Проверяет, является ли URL валидным VK сообществом.

    Args:
        url: URL для проверки

    Returns:
        True если URL валиден
    """
    pattern = r"^https?://vk\.com/(public|club|)[a-zA-Z0-9_]+/?$"
    return bool(re.match(pattern, url))


def extract_telegram_username(url: str) -> str | None:
    """Извлекает username из Telegram URL.

    Args:
        url: Telegram URL

    Returns:
        Username или None
    """
    match = re.search(r"t\.me/([a-zA-Z0-9_]+)", url)
    return match.group(1) if match else None


def extract_vk_id(url: str) -> str | None:
    """Извлекает ID из VK URL.

    Args:
        url: VK URL

    Returns:
        ID сообщества или None
    """
    match = re.search(r"vk\.com/(public|club|)([a-zA-Z0-9_]+)", url)
    return match.group(2) if match else None


def generate_content_hash(text: str | None, media_urls: list[str] | None = None) -> str:
    """Генерирует хеш контента для дедупликации.

    Args:
        text: Текст поста
        media_urls: Список URL медиафайлов

    Returns:
        SHA-256 хеш контента
    """
    content = ""

    if text:
        # Нормализуем текст: убираем лишние пробелы и переводы строк
        normalized_text = " ".join(text.split())
        content += normalized_text

    if media_urls:
        # Добавляем отсортированные URL медиа
        content += "|".join(sorted(media_urls))

    # Генерируем SHA-256 хеш
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sanitize_text(text: str | None) -> str | None:
    """Очищает текст от лишних символов и форматирования.

    Args:
        text: Исходный текст

    Returns:
        Очищенный текст или None
    """
    if not text:
        return None

    # Удаляем множественные переводы строк
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Удаляем пробелы в начале и конце
    text = text.strip()

    return text if text else None
