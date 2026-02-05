from typing import Annotated, Any
from pydantic import Field
from typing_extensions import Doc
from attp.types.frame import AttpFrameDTO
from attp.types.frames.route_mapping import IRouteMapping


class IReadyDTO(AttpFrameDTO):
    proto: Annotated[str, Doc("Protocol ID")] = "ATTP"
    ver: Annotated[str, Doc("Semver for example: 2.0")] = "2.0"
    caps: Annotated[list[str], Doc("Capability flags e.g. ['schemas/msgpack', 'streaming']")] = Field(default_factory=lambda: ['schemas/msgpack', 'streaming'])
    routes: Annotated[list[IRouteMapping], Doc("Remote's route pattern mappings, ATTP converts all routes into binary")]
    data: Annotated[Any, Doc("Any additional data that can `read` payload carry, NOTE: this data will be passed to @AttpEvent() connect callback.")]