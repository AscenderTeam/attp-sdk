import inspect
from typing import Any, Literal
from uuid import UUID


class AttpContext:
    def __init__(
        self, 
        namespace: str,
        session_id: str,
        origin: Literal["client", "server"],
        correlation_id: bytes | None = None,
    ) -> None:
        self.origin = origin
        self.namespace = namespace
        self.session_id = session_id
        self.correlation_id = UUID(bytes=correlation_id) if correlation_id else None
    
    def __setattr__(self, name: str, value: Any) -> None:
        caller = inspect.stack()[1].function
        if caller == "__init__" or caller.startswith("_"):
            super().__setattr__(name, value)
            return
        
        if name in ["session_id", "organization_id", "correlation_id"]:
            raise TypeError(f"'AttpContext' object does not support item assigned for attribute '{name}'")