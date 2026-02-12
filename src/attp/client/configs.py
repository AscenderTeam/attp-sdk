from typing import Any, Callable
from ascender.common import BaseDTO
from pydantic import Field

from attp.client.authenticator import ConnectionAuthenticator
from attp.shared.limits import AttpLimits


class AttpClientConfigs(BaseDTO):
    model_config = {"arbitrary_types_allowed": True}
    
    remote_uri: str # attp://host:port
    namespace: str = "default"
    data: Any | None = None
    authorization: Any | None = None
    auth: Any | None = None
    capabilities: list[str] = Field(default_factory=lambda: ["schema/msgpack", "streaming"])


class ServiceDiscoveryConfigs(BaseDTO):
    model_config = {"arbitrary_types_allowed": True}
    
    peers: list[str | AttpClientConfigs]
    limits: AttpLimits
    authenticator: (
        ConnectionAuthenticator
        | type[ConnectionAuthenticator]
        | Callable[[AttpClientConfigs], ConnectionAuthenticator]
        | None
    ) = None
    reconnection: bool = True
    max_retries: int = 20
