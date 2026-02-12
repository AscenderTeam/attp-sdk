from typing import Annotated, Literal, Sequence

from ascender.core import Inject
from attp.loadbalancer.abc.cacher import StrategyCacher
from attp.loadbalancer.abc.strategy import BalancingStrategy
from attp.loadbalancer.configs import BalancerConfigs
from attp.loadbalancer.evaluator import StrategyEvaluator
from attp.shared.namespaces.dispatcher import NamespaceDispatcher
from attp.shared.sessions.driver import AttpSessionDriver
from attp.types.exceptions.load_balancer import NoBalancingCandidateFound, UnknownStrategyError


class AttpLoadBalancer:
    def __init__(
        self, 
        namespaces: NamespaceDispatcher, 
        strategies: Annotated[Sequence[type[BalancingStrategy]], Inject("ATTP_BALANCING_STRATEGIES")],
        configs: Annotated[BalancerConfigs, Inject("ATTP_BALANCING_CONFIGS")],
        cacher: Annotated[StrategyCacher, Inject("ATTP_BALANCING_CACHER")]
    ) -> None:
        self.namespaces = namespaces
        self.configs = configs
        self.cacher = cacher
        self._strategies = strategies
        
        self.evaluator = StrategyEvaluator(self.cacher, self.configs, self._strategies)
    
    async def acquire_session(
        self, 
        namespace: str,
        *,
        session_id: str | None = None, 
        role: Literal["client", "server"] | None = None
    ):
        candidates = self.namespaces.dispatch(namespace, session_id, role)
        
        if not isinstance(candidates, list):
            if not candidates:
                raise NoBalancingCandidateFound(namespace)
            
            return candidates
        
        default_candidate = candidates.first()
        if not default_candidate:
            raise NoBalancingCandidateFound(namespace)
        
        if not (candidate := await self.evaluator.evaluate(default_candidate, candidates)):
            raise UnknownStrategyError(self.configs.balancing_strategy)
        
        return candidate
    
    def rerotate_session(
        self,
        namespace: str,
        session: AttpSessionDriver
    ):
        self.namespaces.remove_session(namespace, session)
