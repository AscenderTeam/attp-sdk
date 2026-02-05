from ascender.common import BaseDTO
from attp_core.rs_api import Limits


class AttpLimits(BaseDTO):
    max_payload_size: int
    
    def to_model(self):
        return Limits(self.max_payload_size)