from typing import Any
from ascender.common import BaseDTO


class BalancerConfigs(BaseDTO):
    balancing_strategy: str
    strategy_parameters: Any | None = None