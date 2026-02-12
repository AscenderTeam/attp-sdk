import asyncio
from typing import Any, TypeVar

from attp.loadbalancer.abc.cacher import StrategyCacher


T = TypeVar("T")


class SimpleInMemoryCacher(StrategyCacher):
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def store(self, key: str, value: Any) -> Any:
        async with self._lock:
            self._cache[key] = value
        return value

    async def get(self, key: str, *, expected_type: type[T] | None = None) -> T | Any:
        async with self._lock:
            value = self._cache.get(key)

        if expected_type is None or value is None:
            return value

        if isinstance(value, expected_type):
            return value

        return None

    async def increment(self, key: str, *, delta: int = 1, initial: int = 0) -> int:
        async with self._lock:
            current = self._cache.get(key, initial)
            if not isinstance(current, int):
                current = initial
            new_value = current + delta
            self._cache[key] = new_value
            return new_value

    async def keys(self) -> list[str]:
        async with self._lock:
            return list(self._cache.keys())
