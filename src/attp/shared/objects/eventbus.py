import traceback

from logging import Logger
from typing import Annotated, cast

from ascender.core import Inject

from pydantic import ValidationError

from attp.shared.namespaces.router import AttpRouter
from attp.shared.receiver import AttpReceiver
from attp.shared.sessions.additional_mixins import EnhancedFrameTransmitterMixin, StreamingFrameTransmitterMixin

from attp_core.rs_api import PyAttpMessage, AttpCommand

from attp.shared.utils.callbacks import execute_call, execute_event, execute_event_callback
from attp.types.exceptions.attp_exception import AttpException
from attp.types.frames.error import IAttpErr


class EventBus:
    def __init__(self, router: AttpRouter, logger: Annotated[Logger, Inject("ASC_LOGGER")]) -> None:
        self.router = router
        self.logger = logger
    
    async def emit(self, session: EnhancedFrameTransmitterMixin, frame: PyAttpMessage):
        try:
            relevant_route = self.router.relevant_route(frame.route_id, namespace=session.namespace)
            if not relevant_route:
                if frame.correlation_id:
                    await session.send_error(
                        frame.route_id, 
                        error_frame=IAttpErr(
                            code=404, message="Route not found.", detail={
                                "route_id": frame.route_id,
                                "command_type": frame.command_type
                            }
                        )
                    )
                return

            match frame.command_type:
                case AttpCommand.CALL:
                    if relevant_route.route_type != "message":
                        if frame.correlation_id:
                            await session.send_error(
                                frame.route_id, 
                                error_frame=IAttpErr(code=405, message="Wrong ATTP command method.", detail={"allow": relevant_route.route_type}, 
                                retryable=False),
                                correlation_id=frame.correlation_id
                            )
                        return
                    
                    await execute_call(frame, relevant_route, session=cast(StreamingFrameTransmitterMixin, session))
                
                case AttpCommand.EMIT:
                    if relevant_route.route_type != "event":
                        self.logger.error(f"[cyan]ATTP[/] ┆ [red] Wrong attp method was invoked when trying to access EVENT endpoint by route patter [bold cyan]{relevant_route.pattern}[/]")
                        # Since this is an event which has no ACK feature (this is send and forget method) we silently return nothing.
                        return
                    
                    await execute_event(frame, relevant_route)
                
                case AttpCommand.ERR:
                    if relevant_route.route_type in ["err", "connect", "disconnect"]:
                        return
                    
                    error_handler = self.router.get_error_handler(relevant_route.pattern, namespace=relevant_route.namespace)
                    if not error_handler:
                        return
                    
                    await execute_event_callback(frame, error_handler)
                
                case _:
                    if frame.correlation_id:
                        await session.send_error(frame.route_id, error_frame=IAttpErr(code=405, message="Wrong ATTP command method.", retryable=False), correlation_id=frame.correlation_id)
                        
            # TODO (for me tomorrow to fill up)
            # 1. Implement routing and relevant route observation
            # 2. Handle callbacks using specific util tool I defined (`execute_call`)
            # 3. Handle streaming separately
            # 4. Implement `EventBus.run(...)` method (p.s. it should work with multireceiver),
            # 5. Define `Transmitter` object for client proxy and requests. 
            # 6. Define shared decorators.
            # 7. Implement client session driver.
            # 8. Service Discovery COMING SOON...
        except ValidationError as e:
            traceback.print_exc()
            self.logger.exception(e)
            await session.send_error(frame.route_id, error_frame=IAttpErr(code=422, message=e.title, detail=e.errors()), correlation_id=frame.correlation_id)
        
        except AttpException as e:
            traceback.print_exc()
            self.logger.exception(e)
            await session.send_error(frame.route_id, exception=e, correlation_id=frame.correlation_id)
        
        except Exception as e:
            traceback.print_exc()
            self.logger.exception(e)
            await session.send_error(frame.route_id, error_frame=IAttpErr(
                code=500, message="Internal server error", detail=traceback.format_exc()
            ), correlation_id=frame.correlation_id)
    
    async def run(self, receiver: AttpReceiver):
        while True:
            session, msg = await receiver.get()
            
            try:
                await self.emit(session, msg)
            except Exception as e:
                self.logger.exception(e)
                traceback.print_exc()
            finally:
                receiver.task_done()