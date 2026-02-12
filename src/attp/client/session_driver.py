import asyncio
import os
import traceback
from typing import Annotated
from ascender.core import inject
from typing_extensions import Doc
from attp.client.authenticator import ConnectionAuthenticator
from attp.shared.namespaces.router import AttpRouter
from attp.shared.sessions.additional_mixins import EnhancedFrameTransmitterMixin, StreamingFrameTransmitterMixin
from attp.shared.sessions.driver import SessionTerminatorMixin

from attp_core.rs_api import PyAttpMessage, AttpCommand

from attp.types.exceptions.attp_exception import AttpException
from attp.types.exceptions.protocol_error import ProtocolError
from attp.types.frames.accepted import IAcceptedDTO
from attp.types.frames.auth import IAuthDTO
from attp.types.frames.ready import IReadyDTO


class ClientSessionDriver(
    SessionTerminatorMixin,
    EnhancedFrameTransmitterMixin,
    StreamingFrameTransmitterMixin
):
    connection_estabilished_at: Annotated[str | None, Doc("Last connection time according to server's timezone in an ISO-format.")]
    authenticator: ConnectionAuthenticator
    router: AttpRouter = inject(AttpRouter)
    
    async def start(self, capabilities: list, conn_authenticator: ConnectionAuthenticator):
        asyncio.create_task(self.start_listener())
        self._role = "client"
        self._capabilities = capabilities
        self._namespace = conn_authenticator.namespace
        if os.getenv("ATTP_AUTH_DEBUG") == "1":
            log = getattr(self.logger, "info", None)
            if callable(log):
                log(
                    "[cyan]ATTP[/] ┆ Sending AUTH namespace=%s",
                    conn_authenticator.namespace,
                )
        await self.send_frame(
            PyAttpMessage(
                route_id=1, 
                command_type=AttpCommand.AUTH, 
                correlation_id=None, 
                payload=IAuthDTO(
                    namespace=conn_authenticator.namespace, 
                    data=await conn_authenticator.authenticate()
                ).mpd(),
                version=self.version_bytes()
            )
        )
        self.authenticator = conn_authenticator
        try:
            await asyncio.wait_for(self.auth_flag.wait(), timeout=conn_authenticator.AUTH_TIMEOUT)
        except asyncio.TimeoutError:
            raise TimeoutError("Authentication timed out for session {}".format(self.session_id))
        
        return self.namespace, self.session_id
    
    async def _on_event(self, events: list[PyAttpMessage]):
        self.logger.debug(f"[cyan]ATTP[/] ┆ Received a new message from session {self.session_id}")
        
        for event in events:
            if event.route_id == 0 and event.command_type == AttpCommand.READY:
                try:
                    if not event.payload:
                        continue
                    if os.getenv("ATTP_AUTH_DEBUG") == "1":
                        log = getattr(self.logger, "info", None)
                        if callable(log):
                            log("[cyan]ATTP[/] ┆ READY received")
                    self._enqueue_incoming(event)
                    await self._register_connection(IAcceptedDTO.mps(event.payload))
                except Exception as e:
                    traceback.print_exc()
                    # TODO: Implement error reporting
                    await self.handle_disconnect()
                    return
            
            elif event.command_type == AttpCommand.DISCONNECT:
                await self.handle_disconnect()
                return
            elif event.command_type == AttpCommand.ERR:
                self._enqueue_incoming(event)
                return
            else:
                if self.is_authenticated:
                    self._enqueue_incoming(event)

    async def _register_connection(self, frame: IAcceptedDTO):
        super()._register_connection(frame)
        try:
            print("RRR", frame.routes)
            self.router.include_remote_routes(self.namespace, frame.routes, "client")
        except ProtocolError as e:
            await self.send_error(0, exception=AttpException(400, message=str(e), detail=traceback.format_exc(), fatal=True))
            await self.close()
            return
        
        self.auth_flag.set()
        self.connection_estabilished_at = frame.server_time
        
        routes = self.router.get_routes(namespace=self.namespace)
        print("CLIENT REGISTERING ROUTES:", routes)

        await self.send_frame(
            PyAttpMessage(
                route_id=0, 
                command_type=AttpCommand.READY, 
                correlation_id=None, 
                payload=IReadyDTO(
                    data=self.authenticator.data,
                    caps=self.capabilities,
                    routes=routes
                ).mpd(),
                version=self.version_bytes()
            )
        )
