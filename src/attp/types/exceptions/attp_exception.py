from typing import Any

from attp.types.frames.error import IAttpErr


class AttpException(Exception):
    def __init__(
        self,
        code: int,
        *,
        message: str | None = None,
        detail: Any | None = None,
        retryable: bool | None = None,
        fatal: bool | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message or str(code)
        self.detail = detail
        self.retryable = retryable
        self.fatal = fatal
        self.trace_id = trace_id

        # Initialize base Exception with readable message
        super().__init__(self.message)

    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.message}"]

        if self.retryable is not None:
            parts.append(f"retryable={self.retryable}")

        if self.fatal is not None:
            parts.append(f"fatal={self.fatal}")

        if self.trace_id:
            parts.append(f"trace_id={self.trace_id}")

        if self.detail is not None:
            parts.append(f"detail={self.detail}")

        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "retryable": self.retryable,
            "fatal": self.fatal,
            "trace_id": self.trace_id,
        }

    def to_error_frame(self):
        return IAttpErr(code=self.code, message=self.message, detail=self.detail, retryable=self.retryable, fatal=self.fatal)
    
    @staticmethod
    def from_ierr(err: IAttpErr):
        return AttpException(**err.model_dump())