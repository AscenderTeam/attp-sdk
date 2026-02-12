class NoBalancingCandidateFound(Exception):
    def __init__(self, namespace: str) -> None:
        self.namespace = namespace
    
    def __str__(self) -> str:
        return f"No session candidate was found to evaluate for balancing in a namespace {self.namespace}! (Are you sure that there are any active connections in this namespace?)"


class UnknownStrategyError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
    
    def __str__(self) -> str:
        return f"Strategy {self.name} doesn't exist in strategy list, if you are using custom strategy, please define when providing ATTP and make sure names are matching!"