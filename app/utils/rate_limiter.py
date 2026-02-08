# app/utils/rate_limiter.py

import asyncio
import time
from collections import deque
from functools import wraps

from app.utils.logger import logger


class RateLimiter:
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.time()

            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()

            if len(self.requests) >= self.max_requests:
                sleep_time = self.time_window - (now - self.requests[0])
                if sleep_time > 0:
                    logger.debug(f"Rate limit достигнут. Ожидание {sleep_time:.1f}s")
                    await asyncio.sleep(sleep_time)
                    await self.acquire()
                    return

            self.requests.append(now)

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await self.acquire()
            return await func(*args, **kwargs)

        return wrapper


class AdaptiveRateLimiter(RateLimiter):
    def __init__(
        self,
        max_requests: int,
        time_window: int = 60,
        max_retries: int = 5,
        base_delay: float = 1.0,
    ):
        super().__init__(max_requests, time_window)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.consecutive_errors = 0

    async def handle_error(self, error: Exception) -> None:
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
        if self.consecutive_errors > 0:
            logger.debug("Счетчик ошибок сброшен после успешного запроса")
            self.consecutive_errors = 0
