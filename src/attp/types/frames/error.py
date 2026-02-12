from typing import Annotated, Any, Literal
from typing_extensions import Doc
from attp.types.frame import AttpFrameDTO


class IAttpErr(AttpFrameDTO):
    code: Annotated[int, Doc("An HTTP numeric error code.")]

    message: Annotated[str | None, Doc("A human readable summary of the error, can be localized as well.")] = None
    detail: Annotated[Any | None, Doc("A structured diagnostic payload, the response containing more systematic details about error.")] = None

    retryable: Annotated[bool | None, Doc("Can auto-retry safely.")] = None
    fatal: Annotated[bool | None, Doc("Is the error fatal (e.g. decrypt failure, protocol mismatch, banned client or auth-lockout)")] = None

    trace_id: Annotated[str | None, Doc("Anyone can specify custom trace id, might be very useful for some implementations.")] = None

    @staticmethod
    def from_exception():
        return