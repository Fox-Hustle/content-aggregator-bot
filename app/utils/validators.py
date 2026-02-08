# app/utils/validators.py

import hashlib
import re


def validate_telegram_url(url: str) -> bool:
    pattern = r"^https?://t\.me/[a-zA-Z0-9_]+/?$"
    return bool(re.match(pattern, url))


def validate_vk_url(url: str) -> bool:
    pattern = r"^https?://vk\.com/(public|club|)[a-zA-Z0-9_]+/?$"
    return bool(re.match(pattern, url))


def extract_telegram_username(url: str) -> str | None:
    match = re.search(r"t\.me/([a-zA-Z0-9_]+)", url)
    return match.group(1) if match else None


def extract_vk_id(url: str) -> str | None:
    match = re.search(r"vk\.com/(public|club|)([a-zA-Z0-9_]+)", url)
    return match.group(2) if match else None


def generate_content_hash(text: str | None, media_urls: list[str] | None = None) -> str:
    content = ""

    if text:
        normalized_text = " ".join(text.split())
        content += normalized_text

    if media_urls:
        content += "|".join(sorted(media_urls))

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sanitize_text(text: str | None) -> str | None:
    if not text:
        return None

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text if text else None
