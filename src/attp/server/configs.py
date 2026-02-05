from ascender.common import BaseDTO

from attp.shared.limits import AttpLimits


class AttpServerConfigs(BaseDTO):
    host: str = "0.0.0.0"
    port: int = 6563
    limits: AttpLimits