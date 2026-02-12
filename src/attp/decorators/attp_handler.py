from typing import Any, Callable
from ascender.core import ControllerDecoratorHook, inject

from attp.shared.namespaces.router import AttpRouter


class AttpErrorHandler(ControllerDecoratorHook):
    router: AttpRouter = inject(AttpRouter)
    
    def __init__(self, pattern: str, namespace: str = "default") -> None:
        self.pattern = pattern
        self.namespace = namespace
    
    def on_load(self, callable: Callable[..., Any]):
        self.router.add_error_handler(self.pattern, callable, namespace=self.namespace)