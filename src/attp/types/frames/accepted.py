from typing import Annotated
from typing_extensions import Doc
from attp.types.frame import AttpFrameDTO
from attp.types.frames.ready import IReadyDTO


class IAcceptedDTO(IReadyDTO):
    server_time: Annotated[str, Doc("Server time in an ISO format.")]