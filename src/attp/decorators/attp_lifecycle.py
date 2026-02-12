from typing import Any, Callable, Literal
from ascender.core import ControllerDecoratorHook, inject

from attp.client.service_discovery import ServiceDiscovery
from attp.server.attp_server import AttpServer
from attp.shared.namespaces.router import AttpRouter


class AttpLifecycle(ControllerDecoratorHook):
    router: AttpRouter = inject(AttpRouter)
    
    def __init__(self, event: Literal["connect", "disconnect"], namespace: str = "default") -> None:
        self.event = event
        self.namespace = namespace
    
    def on_load(self, callable: Callable[..., Any]):
        inject(AttpServer).activate()
        inject(ServiceDiscovery).activate()
        self.router.add_route(self.event, self.event, callable, namespace=self.namespace) # type: ignore