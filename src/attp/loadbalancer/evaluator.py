from typing import Sequence
from attp.loadbalancer.abc.cacher import StrategyCacher
from attp.loadbalancer.abc.candidate import Candidate
from attp.loadbalancer.abc.strategy import BalancingStrategy
from attp.loadbalancer.configs import BalancerConfigs
from attp.shared.utils.qsequence import QSequence


class StrategyEvaluator:
    def __init__(
        self,
        cacher: StrategyCacher, 
        config: BalancerConfigs, 
        strategies: Sequence[type[BalancingStrategy]]
    ) -> None:
        self.cacher = cacher
        self.strategies = strategies
        self.config = config
        self.used_strategy = None
    
    async def evaluate(self, default: Candidate, candidates: QSequence[Candidate]):
        if self.used_strategy and self.used_strategy.name == self.config.balancing_strategy:
            return await self.used_strategy.balance(default, candidates)
        
        for strategy in self.strategies:
            if getattr(strategy, "name", "none") == self.config.balancing_strategy:
                instance = strategy(self.config.strategy_parameters, cacher=self.cacher)
                self.used_strategy = instance
                
                return await instance.balance(default, candidates)