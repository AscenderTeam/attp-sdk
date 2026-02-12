from ascender.common import BaseDTO
from attp_core.rs_api import Limits
from pydantic import Field


class AttpLimits(BaseDTO):
    max_payload_size: int = Field(default_factory=lambda: 10 * 1024 * 1024)
    
    def to_model(self):
        return Limits(self.max_payload_size)