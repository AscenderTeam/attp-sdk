from abc import ABC, abstractmethod
from typing import Any


class AuthStrategy(ABC):
    AUTH_TIMEOUT: float
    
    @abstractmethod
    async def authenticate(self, namespace: str, frame: Any) -> bool:
        ...

    async def on_read(self, namespace: str, frame) -> Any:
        return None