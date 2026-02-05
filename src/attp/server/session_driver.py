import asyncio
from logging import Logger
import traceback
from typing import Any, Callable, Self

from ascender.core import inject

from attp.server.abc.auth_strategy import AuthStrategy
from attp.shared.receiver import AttpReceiver

from attp_core.rs_api import Session, PyAttpMessage, AttpCommand

from attp.shared.utils.qsequence import QSequence
from attp.types.frames.auth import IAuthDTO
from attp.types.frames.ready import IReadyDTO


class ServerSessionDriver:
    _session: Session | None
    
    logger: Logger
    
    incoming_listener: asyncio.Queue[PyAttpMessage | None]
    
    def __init__(
        self,
        session: Session,
        strategy: AuthStrategy,
        on_termination: Callable[[Self], Any] | None = None
    ) -> None:
        self._session = session
        self._capabilities = ["schema/msgpack", "streaming"]
        self._version = None
        
        self._namespace = "default"
        
        self.incoming_listener = asyncio.Queue()
        self.strategy = strategy
        self.on_termination = on_termination
        self.logger = inject("ASC_LOGGER")
        
        self.auth_flag = asyncio.Event()
    
    @property
    def is_authenticated(self):
        return self.auth_flag.is_set()
    
    @property
    def session_id(self):
        return self._session.session_id if self._session else None
    
    @property
    def capabilities(self):
        return self._capabilities
    
    @property
    def namespace(self):
        return self._namespace
    
    @property
    def version(self):
        return self._version or "1.0"
    
    # ================== Frame transmitter methods ================== #
    async def send_frame(self, frame: PyAttpMessage):
        if not self._session:
            raise ConnectionError("Cannot send an ATTP message to dead session!")
        await self._session.send(frame)

    async def send_batch(self, frames: QSequence[PyAttpMessage]):
        if not self._session:
            raise ConnectionError("Cannot send an ATTP message to dead session!")
        await self._session.send_batch(frames.to_list())
    
    # ================== External Entrypoint Methods ================== #
    async def listen(self, receiver: AttpReceiver[tuple["ServerSessionDriver", PyAttpMessage]]):
        self.logger.debug("[cyan]ATTP[/] ┆ Running listener for session %s", self.session_id)
        while self.is_authenticated:
            frame = await self.incoming_listener.get()
            if frame is None:
                break
            
            self.logger.debug("[cyan]ATTP[/] ┆ Emitting the incoming frame in the listener to responder...")
            receiver.on_next((self, frame))
    
    async def start(self):
        try:
            await asyncio.wait_for(self.auth_flag.wait(), timeout=self.strategy.AUTH_TIMEOUT)
        except asyncio.TimeoutError:
            raise TimeoutError("Authentication timed out for session {}".format(self.session_id))
        
        return self.namespace, self.session_id
    
    # ================== Connection Lifecycle ================== #
    async def handle_disconnect(self):
        session_label = self.session_id
        self.logger.info("[cyan]ATTP[/] ┆ Session %s requested disconnect", session_label)
        if self._session:
            self.stop_listener()
            self._session.disconnect()
        await self._terminate()
        self._session = None
        self.auth_flag.clear()
    
    # ================== Listener Lifecycle ================== #
    async def start_listener(self):
        if not self._session:
            raise ConnectionError(f"Cannot perform any actions over dead ATTP session {self}")
        
        self._loop = asyncio.get_running_loop()
        self._session.add_event_handler(self._on_event)
        try:
            await asyncio.gather(
                self._session.start_handler(),
                self._session.start_listener()
            )
        except (ConnectionResetError, OSError):
            self.logger.info("[cyan]ATTP[/] ┆ Session connections lost or disconnected")
            await self.handle_disconnect()
    
    def stop_listener(self):
        if not self._session:
            return
        self._enqueue_incoming(None)
        
        self._session.stop_listener()
    
    # ================== Encapsulated operative methods ================== #
    def _register_connection(self, frame: IReadyDTO):
        if frame.proto != "ATTP":
            return
        
        self._capabilities = frame.caps
        self._version = frame.ver
    
    def _enqueue_incoming(self, event: PyAttpMessage | None) -> None:
        loop = self._loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(self.incoming_listener.put_nowait, event)
        else:
            self.incoming_listener.put_nowait(event)
    
    async def _authenticate(self, frame: IAuthDTO):
        _access = await self.strategy.authenticate(namespace=frame.namespace, frame=frame.data)
        
        if _access:
            self.auth_flag.set()
            self._namespace = frame.namespace
    
    async def _terminate(self):
        if self.on_termination:
            try:
                await self.on_termination(self)
            except Exception:
                traceback.print_exc()
    
    async def _on_event(self, events: list[PyAttpMessage]):
        self.logger.debug(f"[cyan]ATTP[/] ┆ Received a new message from session {self.session_id}")
        
        for event in events:
            if event.command_type == AttpCommand.AUTH:
                if self.is_authenticated:
                    continue
                
                try:
                    if not event.payload:
                        pass
                        continue
                    await self._authenticate(IAuthDTO.mps(event.payload))
                except Exception as e:
                    traceback.print_exc()
                    # TODO: Implement error reporting
                    continue
            
            elif event.route_id == 0 and event.command_type == AttpCommand.READY:
                try:
                    if not event.payload:
                        continue
                    
                    self._enqueue_incoming(event)
                    self._register_connection(IReadyDTO.mps(event.payload))
                except Exception as e:
                    traceback.print_exc()
                    # TODO: Implement error reporting
                    await self.handle_disconnect()
                    return
            
            elif event.command_type == AttpCommand.DISCONNECT:
                await self.handle_disconnect()
                return
            
            else:
                if self.is_authenticated:
                    self._enqueue_incoming(event)
