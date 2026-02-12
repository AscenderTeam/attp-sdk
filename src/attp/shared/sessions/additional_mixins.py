from typing import Any
from uuid import uuid4

import msgpack
from attp.shared.sessions.driver import FrameTransmitterMixin
from attp.types.exceptions.attp_exception import AttpException
from attp.types.frame import AttpFrameDTO
from attp.types.frames.error import IAttpErr

from attp_core.rs_api import PyAttpMessage, AttpCommand

from attp.types.streaming_signature import StreamingSignature


class EnhancedFrameTransmitterMixin(FrameTransmitterMixin):
    
    async def send_call(
        self,
        route_id: int,
        data: AttpFrameDTO | Any | None,
        *,
        correlation_id: bytes | None = None
    ) -> bytes:
        """
        Sends CALL command to the receiving side.

        Args:
            route_id (int): The mandatory ID of the route.
            data (AttpFrameDTO): Data frame of ATTP message.
            correlation_id (bytes | None, optional): The mandatory correlation ID of the CALL message. Defaults to None. If None was passed, correlation ID will be auto-generated

        Raises:
            ValueError: If reserved route_id was used.

        Returns:
            bytes: Correlation ID that was either passed or auto-generated.
        """
        if route_id < 1:
            raise ValueError("Cannot use reserved `route_id`s 0 and 1, they are not meant for Attp `CALL` requests.")

        if not correlation_id:
            correlation_id = uuid4().bytes
        
        await self.send_frame(
            PyAttpMessage(
                route_id=route_id,
                command_type=AttpCommand.CALL,
                correlation_id=correlation_id,
                payload=data.mpd() if isinstance(data, AttpFrameDTO) else (msgpack.packb(data) if data is not None else None),
                version=self.version_bytes()
            )
        )
        
        return correlation_id
    
    async def send_event(
        self,
        route_id: int,
        data: AttpFrameDTO | Any | None,
    ):
        """
        Send EMIT frame to the receiver side.
        
        NOTE: Messages (events) that were sent using EMIT type of command are usually one-sided.
        Which means there's no ACK mechanism for them, so make sure these messages aren't crucial.

        Args:
            route_id (int): ID of the route, NOTE: 1 or 0 are reserved and can't be used.
            data (AttpFrameDTO): Data frame of an ATTP message.
        """
        if route_id < 1:
            raise ValueError("Cannot use reserved `route_id`s 0 and 1, they are not meant for Attp `CALL` requests.")

        await self.send_frame(
            PyAttpMessage(
                route_id=route_id,
                command_type=AttpCommand.EMIT,
                correlation_id=None,
                payload=data.mpd() if isinstance(data, AttpFrameDTO) else (msgpack.packb(data) if data is not None else None),
                version=self.version_bytes()
            )
        )

    
    async def send_error(
        self,
        route_id: int = 0,
        *,
        exception: AttpException | None = None,
        error_frame: IAttpErr | None = None,
        correlation_id: bytes | None = None,
    ):
        if not exception and not error_frame:
            raise TypeError("One of two arguments are required `exception` or `error_frame`")
        
        await self.send_frame(
            PyAttpMessage(
                route_id=route_id, 
                command_type=AttpCommand.ERR, 
                correlation_id=correlation_id, 
                payload=error_frame.mpd() if error_frame else exception.to_error_frame().mpd(), # type: ignore
                version=self.version_bytes()
            )
        )


class StreamingFrameTransmitterMixin(FrameTransmitterMixin):
    
    async def start_stream(self, route_id: int, correlation_id: bytes | None = None):
        if route_id < 1:
            raise ValueError("Cannot use reserved `route_id`s 0 and 1, they are not meant for Attp `CALL` requests.")

        if not correlation_id:
            correlation_id = uuid4().bytes
        
        await self.send_frame(PyAttpMessage(
            route_id=route_id, command_type=AttpCommand.STREAMBOS,
            correlation_id=correlation_id,
            payload=None, version=self.version_bytes()
        ))
        
        return StreamingSignature(route_id=route_id, correlation_id=correlation_id)
    
    async def send_chunk(self, info: StreamingSignature, data: AttpFrameDTO | Any):
        await self.send_frame(PyAttpMessage(
            route_id=info.route_id,
            command_type=AttpCommand.CHUNK,
            correlation_id=info.correlation_id,
            payload=data.mpd() if isinstance(data, AttpFrameDTO) else msgpack.packb(data),
            version=self.version_bytes()
        ))
    
    async def end_stream(self, info: StreamingSignature):
        await self.send_frame(PyAttpMessage(
            route_id=info.route_id,
            command_type=AttpCommand.STREAMEOS,
            correlation_id=info.correlation_id,
            payload=None,
            version=self.version_bytes()
        ))
