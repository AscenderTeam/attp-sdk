from ascender.common import BaseDTO


class StreamingSignature(BaseDTO):
    route_id: int
    correlation_id: bytes
