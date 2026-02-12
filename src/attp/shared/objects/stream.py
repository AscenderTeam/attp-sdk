from typing import AsyncIterable, Iterable, TypeAlias
from collections.abc import AsyncIterable as AsyncIterableABC, AsyncIterator as AsyncIteratorABC

from attp.types.frame import AttpFrameDTO


IterateWrapper: TypeAlias = (
    Iterable[AttpFrameDTO] | AsyncIterable[AttpFrameDTO]
)


class StreamObject:
    def __init__(
        self,
        _iterable: IterateWrapper | None = None
    ) -> None:
        self._iterable = _iterable
        self.is_async = False
        
        if isinstance(_iterable, (AsyncIterableABC, AsyncIterableABC)):
            self.is_async = True
    
    def iterate(self) -> Iterable[AttpFrameDTO] | None:
        return self._iterable # type: ignore
    
    def aiterate(self) -> AsyncIterable[AttpFrameDTO] | None:
        return self._iterable # type: ignore