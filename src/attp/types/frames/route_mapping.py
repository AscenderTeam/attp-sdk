from attp.types.frame import AttpFrameDTO
from attp.types.routes import AttpRouteMapping, RouteType


class IRouteMapping(AttpFrameDTO):
    pattern: str
    route_id: int
    route_type: RouteType
    namespace: str
    
    @staticmethod
    def from_route_mapper(mapper: AttpRouteMapping):
        return IRouteMapping(pattern=mapper.pattern, route_id=mapper.route_id, route_type=mapper.route_type, namespace=mapper.namespace)