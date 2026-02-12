from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

# from core.attp.interfaces.handshake.mapping import IRouteMapping


RouteType: TypeAlias = Literal["event", "message", "err", "disconnect", "connect"]


@dataclass(frozen=False)
class AttpRouteMapping:
    pattern: str
    route_id: int
    route_type: RouteType
    callback: Any
    namespace: str

    def __eq__(self, value: object) -> bool:
        if isinstance(value, AttpRouteMapping):
            return value.pattern == self.pattern
        
        return False
    
    def __hash__(self) -> int:
        return hash(self.pattern)