from typing import Annotated, Any
from typing_extensions import Doc
from attp.types.frame import AttpFrameDTO


class IAuthDTO(AttpFrameDTO):
    namespace: Annotated[str, Doc("A short, string namespace of the connection that will current connection be categorized to.")]
    data: Annotated[Any, Doc("Authentication credentails and data that will be used to verify the legitimacy of the connection.")]