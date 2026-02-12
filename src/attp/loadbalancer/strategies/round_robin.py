from typing import Any
from attp.loadbalancer.abc.cacher import StrategyCacher
from attp.loadbalancer.abc.candidate import Candidate
from attp.loadbalancer.abc.strategy import BalancingStrategy
from attp.shared.utils.qsequence import QSequence


class BasicRoundRobinStrategy(BalancingStrategy):
    name: str = "round-robin"
    
    def __init__(self, configs: Any, cacher: StrategyCacher) -> None:
        self.configs = configs
        self.cacher = cacher
    
    async def next_index(self, total: int) -> int:
        counter = await self.cacher.increment("round_robin_index", delta=1, initial=0)
        return (counter - 1) % total
    
    async def balance(self, default: Candidate, candidates: QSequence[Candidate]) -> Candidate:
        total = candidates.count()
        try:
            if total <= 0:
                return default

            index = await self.next_index(total)
            return candidates[index]
        
        except Exception:
            return default
