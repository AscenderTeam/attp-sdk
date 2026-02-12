from collections import defaultdict
from hashlib import blake2b
from threading import Lock
from typing import Any, Callable, Iterable, Literal, Sequence
from attp.shared.utils.qsequence import QSequence
from attp.types.exceptions.protocol_error import ProtocolError
from attp.types.frames.route_mapping import IRouteMapping
from attp.types.routes import AttpRouteMapping, RouteType


class AttpRouter:
    routes: QSequence[AttpRouteMapping]
    remote_routes_client: dict[str, QSequence[IRouteMapping]]
    remote_routes_server: dict[str, QSequence[IRouteMapping]]
    errors: dict[str, QSequence[tuple[str, Callable[..., Any]]]]
    
    def __init__(self) -> None:
        self.routes = QSequence()
        self.remote_routes_client = defaultdict(QSequence[IRouteMapping])
        self.remote_routes_server = defaultdict(QSequence[IRouteMapping])
        self.errors = defaultdict(QSequence[tuple[str, Callable[..., Any]]])
        self._remote_routes_lock = Lock()
        self.increment_index = 2 # 0 and 1 are reserved for:
        # 1. Zero's are reserved for connect/disconnect events.
        # 2. One's are reserved for authentication and authentication errors

    def add_route(
        self, 
        route_type: RouteType, 
        pattern: str, 
        callback: Callable[..., Any],
        *,
        namespace: str | None = None
    ):
        if pattern in ("connect", "disconnect") and route_type in ("connect", "disconnect"):
            self.routes.append(AttpRouteMapping(pattern, 0, route_type, callback, namespace or "default"))
            return
        
        self.routes.append(AttpRouteMapping(pattern, self.increment_index, route_type, callback, namespace or "default"))
        self.increment_index += 1
    
    def add_event(
        self,
        pattern: str,
        callback: Callable[..., Any],
        *,
        namespace: str | None = None
    ):
        self.add_route("event", pattern, callback, namespace=namespace)
    
    def add_error_handler(
        self,
        pattern: str,
        callback: Callable[..., Any],
        *,
        namespace: str | None = None
    ):
        self.errors[pattern].append((namespace or "default", callback))
    
    def include_remote_routes(
        self,
        namespace: str,
        routes: Sequence[IRouteMapping],
        role: Literal["client", "server"]
    ):
        if role == "client":
            target = self.remote_routes_client
        elif role == "server":
            target = self.remote_routes_server
        else:
            raise ValueError("role must be 'client' or 'server'")

        def _digest_routes(items: Iterable[IRouteMapping] | Iterable[AttpRouteMapping]):
            hasher = blake2b(digest_size=16)
            update = hasher.update
            for route in items:
                update(route.route_id.to_bytes(8, "little", signed=False))
                update(route.route_type.encode("utf-8"))
                update(b"\x00")
                update(route.pattern.encode("utf-8"))
                update(b"\x00")
                update(route.namespace.encode("utf-8"))
                update(b"\x00")
            return hasher.digest()

        with self._remote_routes_lock:
            existing = target.get(namespace)
            if existing and len(existing):
                if _digest_routes(routes) != _digest_routes(existing):
                    raise ProtocolError("RouteMatchError", f"Remote routes mismatch for namespace {namespace!r}.")
                return

            target[namespace] = QSequence(routes)
    
    def dispatch(
        self,
        pattern: str,
        route_type: RouteType,
        *,
        namespace: str = "default",
        role: Literal["client", "server"] = "server"
    ):
        target = self.remote_routes_client if role == "client" else self.remote_routes_server
        print(target[namespace], role)
        return target[namespace].filter(lambda r: r.pattern == pattern and r.route_type == route_type and r.namespace == namespace).last()
    
    def relevant_route(self, route_id: int, namespace: str = "default"):
        # print("RELEVANT ROUTE SEEK", self.routes, route_id, namespace)
        return self.routes.filter(lambda r: r.route_id == route_id and r.namespace == namespace).last()
    
    def get_error_handler(self, pattern: str, namespace: str = "default"):
        return self.errors[pattern].where(lambda n: n[0] == namespace).map(lambda n: n[1]).last()
    
    def get_routes(self, namespace: str = "default"):
        return self.routes.filter(lambda n: n.namespace == namespace).map(lambda r: IRouteMapping.from_route_mapper(r)).to_list()
