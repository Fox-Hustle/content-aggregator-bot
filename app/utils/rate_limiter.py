# app/utils/rate_limiter.py

"""Rate limiter для контроля частоты запросов к API."""

import asyncio
import time
from collections import deque
from functools import wraps

from app.utils.logger import logger


class RateLimiter:
    """Ограничитель частоты запросов."""

    def __init__(self, max_requests: int, time_window: int = 60):
        """Инициализация rate limiter.

        Args:
            max_requests: Максимальное количество запросов
            time_window: Временное окно в секундах (по умолчанию 60)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Ожидает возможности выполнить запрос с учетом лимита."""
        async with self._lock:
            now = time.time()

            # Удаляем старые запросы за пределами временного окна
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()

            # Если достигли лимита - ждем
            if len(self.requests) >= self.max_requests:
                sleep_time = self.time_window - (now - self.requests[0])
                if sleep_time > 0:
                    logger.debug(f"Rate limit достигнут. Ожидание {sleep_time:.1f}s")
                    await asyncio.sleep(sleep_time)
                    # Рекурсивно пробуем снова
                    await self.acquire()
                    return

            # Записываем новый запрос
            self.requests.append(now)

    def __call__(self, func):
        """Декоратор для применения rate limiting к функции."""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            await self.acquire()
            return await func(*args, **kwargs)

        return wrapper


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter с экспоненциальной задержкой при ошибках."""

    def __init__(
        self,
        max_requests: int,
        time_window: int = 60,
        max_retries: int = 5,
        base_delay: float = 1.0,
    ):
        """Инициализация адаптивного rate limiter.

        Args:
            max_requests: Максимальное количество запросов
            time_window: Временное окно в секундах
            max_retries: Максимальное количество повторных попыток
            base_delay: Базовая задержка для экспоненциального backoff
        """
        super().__init__(max_requests, time_window)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.consecutive_errors = 0

    async def handle_error(self, error: Exception) -> None:
        """Обрабатывает ошибку и применяет экспоненциальную задержку.

        Args:
            error: Возникшая ошибка
        """
        self.consecutive_errors += 1

        if self.consecutive_errors > self.max_retries:
            logger.error(
                f"Превышено количество попыток ({self.max_retries}). "
                f"Последняя ошибка: {error}"
            )
            raise

        delay = self.base_delay * (2 ** (self.consecutive_errors - 1))
        logger.warning(
            f"Ошибка #{self.consecutive_errors}: {error}. Повтор через {delay:.1f}s"
        )
        await asyncio.sleep(delay)

    async def reset_errors(self) -> None:
        """Сбрасывает счетчик ошибок после успешного запроса."""
        if self.consecutive_errors > 0:
            logger.debug("Счетчик ошибок сброшен после успешного запроса")
            self.consecutive_errors = 0
