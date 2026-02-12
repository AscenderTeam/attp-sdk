from abc import ABC, abstractmethod
from typing import Any

from attp.loadbalancer.abc.cacher import StrategyCacher
from attp.loadbalancer.abc.candidate import Candidate
from attp.shared.utils.qsequence import QSequence


class BalancingStrategy(ABC):
    name: str
    
    @abstractmethod
    def __init__(
        self, 
        configs: Any,
        cacher: StrategyCacher,
    ) -> None:
        ...
    
    @abstractmethod
    async def balance(self, default: Candidate, candidates: QSequence[Candidate]) -> Candidate:
        pass