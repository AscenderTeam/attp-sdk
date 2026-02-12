class ProtocolError(Exception):
    def __init__(self, type: str, reason: str | None = None) -> None:
        self.type = type
        self.reason = reason
    
    def __str__(self) -> str:
        return f"[{self.type}] {self.reason or 'Unknown error.'}"


class SerializationError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
    
    def __str__(self) -> str:
        return f"[ATTPSerializationFault] {self.detail}"