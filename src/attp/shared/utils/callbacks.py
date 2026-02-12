from typing import TYPE_CHECKING, Any, Callable

import msgpack
from attp_core.rs_api import PyAttpMessage, AttpCommand

from attp.shared.objects.stream import StreamObject
from attp.shared.sessions.additional_mixins import StreamingFrameTransmitterMixin
from attp.shared.utils.executor import execute_validated
from attp.types.frame import AttpFrameDTO
from attp.types.routes import AttpRouteMapping


async def execute_call(
    frame: PyAttpMessage, 
    mapping: AttpRouteMapping,
    *, session: StreamingFrameTransmitterMixin
):
    callback = mapping.callback
    
    payload = {}
    
    if frame.payload:
        payload = msgpack.unpackb(frame.payload, raw=False)
    
    response = await execute_validated(callback, payload, frame=frame)
    
    if isinstance(response, StreamObject):

        assert frame.correlation_id
        _signature = await session.start_stream(route_id=frame.route_id, correlation_id=frame.correlation_id)

        if response.is_async:
            iterable = response.aiterate()
            if not iterable:
                return
            
            async for chunk in iterable:
                await session.send_chunk(
                    info=_signature,
                    data=chunk
                )
        else:
            iterable = response.iterate()
            for chunk in iterable:  # type: ignore
                await session.send_chunk(
                    info=_signature,
                    data=chunk
                )

        await session.end_stream(_signature)
        return
    
    if isinstance(response, AttpFrameDTO):
        response_payload = response.mpd()
    elif response is None:
        response_payload = None
    elif isinstance(response, (bytes, bytearray)):
        response_payload = bytes(response)
    else:
        response_payload = msgpack.packb(response, use_bin_type=True)

    assert frame.correlation_id
    await session.send_frame(PyAttpMessage(
        route_id=frame.route_id,
        command_type=AttpCommand.ACK,
        correlation_id=frame.correlation_id,
        payload=response_payload,
        version=session.version_bytes(),
    ))

async def execute_event(
    frame: PyAttpMessage,
    mapping: AttpRouteMapping
):
    callback = mapping.callback
    
    payload = {}
    
    if frame.payload:
        payload = msgpack.unpackb(frame.payload, raw=False)
    
    await execute_validated(callback, payload, frame=frame)


async def execute_event_callback(
    frame: PyAttpMessage,
    callback: Callable[..., Any]
):
    payload = {}
    
    if frame.payload:
        payload = msgpack.unpackb(frame.payload, raw=False)
    
    await execute_validated(callback, payload, frame=frame)
