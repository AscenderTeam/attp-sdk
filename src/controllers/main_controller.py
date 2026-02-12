from ascender.core import Controller, Get

from attp.decorators.attp_call import AttpCall
from attp.decorators.attp_event import AttpEvent
from attp.decorators.attp_handler import AttpErrorHandler
from attp.decorators.attp_lifecycle import AttpLifecycle
from attp.shared.transmitter import AttpTransmitter
from attp.types.frame import AttpFrameDTO
from attp.types.frames.error import IAttpErr


class EchoRequest(AttpFrameDTO):
    message: str


class EchoResponse(AttpFrameDTO):
    message: str


class NotifyEvent(AttpFrameDTO):
    event: str


@Controller(
    standalone=True,
    guards=[],
    imports=[],
    providers=[],
)
class MainController:
    def __init__(self, transmitter: AttpTransmitter,):  
        self.transmitter = transmitter
    
    @Get("try")
    async def try_echo(self):
        resp = await self.transmitter.send(
            "echo", 
            EchoRequest(message="test"), 
            namespace="peer-1", 
            expected_response=EchoResponse
        )
        return resp
        
    @AttpCall("echo", namespace="peer-1")
    async def echo(self, message: str):
        print(message)
        return EchoResponse(message=message)

    @AttpEvent("notify")
    async def notify(self, payload: NotifyEvent):
        self._last_event = payload.event

    @AttpErrorHandler("echo")
    async def echo_error(self, err: IAttpErr):
        self._last_error = err

    @AttpLifecycle("connect", namespace="peer-1")
    async def on_connect(self, payload: dict | None = None):
        self._last_connect = payload

    @AttpLifecycle("disconnect", namespace="peer-1")
    async def on_disconnect(self, payload: dict | None = None):
        self._last_disconnect = payload
