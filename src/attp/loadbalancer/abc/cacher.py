from abc import ABC, abstractmethod
from typing import Any, TypeVar


T = TypeVar("T")


class StrategyCacher(ABC):
    
    @abstractmethod
    async def store(self, key: str, value: Any) -> Any:
        ...
    
    @abstractmethod
    async def get(self, key: str, *, expected_type: type[T] | None = None) -> T | Any:
        ...

    @abstractmethod
    async def increment(self, key: str, *, delta: int = 1, initial: int = 0) -> int:
        ...
    
    async def keys(self):
        raise NotImplementedError
