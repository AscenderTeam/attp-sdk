import asyncio
import os
from datetime import datetime
import traceback

from ascender.core import inject

from attp.server.abc.auth_strategy import AuthStrategy

from attp_core.rs_api import PyAttpMessage, AttpCommand

from attp.shared.namespaces.router import AttpRouter
from attp.shared.sessions.additional_mixins import EnhancedFrameTransmitterMixin, StreamingFrameTransmitterMixin
from attp.shared.sessions.driver import SessionTerminatorMixin
from attp.types.exceptions.attp_exception import AttpException
from attp.types.exceptions.protocol_error import ProtocolError
from attp.types.frames.accepted import IAcceptedDTO
from attp.types.frames.auth import IAuthDTO
from attp.types.frames.error import IAttpErr
from attp.types.frames.ready import IReadyDTO


class ServerSessionDriver(
    SessionTerminatorMixin,
    EnhancedFrameTransmitterMixin,
    StreamingFrameTransmitterMixin
):
    auth_strategy: AuthStrategy = inject("ATTP_AUTH_STRATEGY")
    router: AttpRouter = inject(AttpRouter)
    
    async def start(self):
        asyncio.create_task(self.start_listener())
        try:
            await asyncio.wait_for(self.auth_flag.wait(), timeout=self.auth_strategy.AUTH_TIMEOUT)
        except asyncio.TimeoutError:
            raise TimeoutError("Authentication timed out for session {}".format(self.session_id))
        self._role = "server"
        return self.namespace, self.session_id
    
    async def _authenticate(self, frame: IAuthDTO):
        try:
            _allowed = await self.auth_strategy.authenticate(frame.namespace, frame.data)
        except Exception as e:
            traceback.print_exc()
            await self.send_error(route_id=0, error_frame=IAttpErr(
                code=401, 
                message="Authentication failed",
                detail={"reason": str(e), "exception": traceback.format_exc()}
            ))
            return
        if _allowed:
            if os.getenv("ATTP_AUTH_DEBUG") == "1":
                self.logger.info(
                    "[cyan]ATTP[/] ┆ AUTH OK namespace=%s session=%s",
                    frame.namespace,
                    self.session_id,
                )
            self.auth_flag.set()
            self._namespace = frame.namespace
            routes = self.router.get_routes(namespace=self.namespace)
            
            print("REGISTERING ROUTES:", routes)
            
            await self.send_frame(PyAttpMessage(
                route_id=0, 
                command_type=AttpCommand.READY,
                correlation_id=None, 
                payload=IAcceptedDTO(
                    caps=self._capabilities, 
                    server_time=datetime.now().isoformat(),
                    routes=routes,
                    data=None, # TODO: Link this with `connect` callback which is executed by eventbus.
                ).mpd(),
                version=self.version_bytes()
            ))
            return
        
        await self.send_error(route_id=0, error_frame=IAttpErr(
            code=401, 
            message="Authentication failed",
            detail={"reason": "Invalid authentication credentials."}
        ))

    async def _on_event(self, events: list[PyAttpMessage]):
        self.logger.debug(f"[cyan]ATTP[/] ┆ Received a new message from session {self.session_id}")
        try:
            for event in events:
                if event.command_type == AttpCommand.AUTH:
                    if self.is_authenticated:
                        continue
                    
                    try:
                        if not event.payload:
                            pass
                            continue
                        auth_frame = IAuthDTO.mps(event.payload)
                        if os.getenv("ATTP_AUTH_DEBUG") == "1":
                            data = auth_frame.data
                            node_id = data.get("node_id") if isinstance(data, dict) else None
                            self.logger.info(
                                "[cyan]ATTP[/] ┆ AUTH received namespace=%s node_id=%s",
                                auth_frame.namespace,
                                node_id,
                            )
                        await self._authenticate(auth_frame)
                    except Exception as e:
                        traceback.print_exc()
                        # TODO: Implement error reporting
                        continue
                
                elif event.route_id == 0 and event.command_type == AttpCommand.READY:
                    try:
                        if not event.payload:
                            continue
                        
                        self._enqueue_incoming(event)
                        await self._register_connection(IReadyDTO.mps(event.payload))
                    except Exception as e:
                        traceback.print_exc()
                        # TODO: Implement error reporting
                        await self.close()
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
        except Exception:
            traceback.print_exc()
    
    async def _register_connection(self, frame: IReadyDTO):
        super()._register_connection(frame)
        try:
            print("RRR", frame.routes)
            self.router.include_remote_routes(self.namespace, frame.routes, "server")
        except ProtocolError as e:
            await self.send_error(0, exception=AttpException(400, message=str(e), detail=traceback.format_exc(), fatal=True))
            await self.close()