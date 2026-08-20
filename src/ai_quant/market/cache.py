from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Dict, Generic, List, Tuple, TypeVar

T = TypeVar("T")


class AsyncTTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float, max_size: int = 1024):
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._values: Dict[str, Tuple[float, T]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
    ) -> T:
        now = time.monotonic()
        cached = self._values.get(key)
        if cached and cached[0] > now:
            return cached[1]

        async with self._guard:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            lock = self._locks[key]

        async with lock:
            now = time.monotonic()
            cached = self._values.get(key)
            if cached and cached[0] > now:
                return cached[1]

            value = await factory()
            if len(self._values) >= self._max_size:
                self._evict_expired()
            if len(self._values) >= self._max_size:
                oldest_key = min(
                    self._values,
                    key=lambda k: self._values[k][0],
                )
                self._values.pop(oldest_key, None)

            self._values[key] = (
                time.monotonic() + self._ttl,
                value,
            )
            return value

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired: List[str] = [
            key for key, (expires, _) in self._values.items() if expires <= now
        ]
        for key in expired:
            self._values.pop(key, None)
