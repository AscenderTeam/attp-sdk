from ascender.common import BaseDTO

from attp.server.abc.auth_strategy import AuthStrategy
from attp.shared.limits import AttpLimits


class AttpServerConfigs(BaseDTO):
    model_config = {"arbitrary_types_allowed": True}
    
    host: str = "0.0.0.0"
    port: int = 6563
    limits: AttpLimits
    authentication: AuthStrategy | None = None
    verbose: bool = False
    verbosity_level: str = "info"