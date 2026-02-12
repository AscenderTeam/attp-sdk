import asyncio
from attp.shared.objects.eventbus import EventBus
from attp.shared.receiver import AttpReceiver
from attp.shared.sessions.additional_mixins import EnhancedFrameTransmitterMixin
from attp.shared.sessions.driver import AttpSessionDriver

from attp_core.rs_api import PyAttpMessage


import asyncio
import traceback
from typing import TypeAlias, cast

from attp_core.rs_api import PyAttpMessage, AttpCommand

from attp.shared.transmitter import AttpTransmitter
from attp.types.frames.error import IAttpErr


ReceiverPayload: TypeAlias = tuple[AttpSessionDriver | EnhancedFrameTransmitterMixin, PyAttpMessage]


class AttpFrameDispatcher:
    def __init__(self, eventbus: EventBus, transmitter: AttpTransmitter) -> None:
        self.eventbus = eventbus
        self.transmitter = transmitter

        self._tasks: dict[AttpReceiver[ReceiverPayload], asyncio.Task] = {}

    def start(self, receiver: AttpReceiver[ReceiverPayload]) -> None:
        """
        Attach and start consuming a new receiver.
        Safe to call multiple times.
        """
        if receiver in self._tasks and not self._tasks[receiver].done():
            return

        task = asyncio.create_task(self._run(receiver))
        self._tasks[receiver] = task


    def stop(self, receiver: AttpReceiver[ReceiverPayload]) -> None:
        """
        Stop consuming specific receiver.
        """
        task = self._tasks.pop(receiver, None)
        if task and not task.done():
            task.cancel()


    def stop_all(self) -> None:
        """
        Stop dispatcher entirely.
        """
        for task in self._tasks.values():
            if not task.done():
                task.cancel()

        self._tasks.clear()


    async def _run(self, receiver: AttpReceiver[ReceiverPayload]) -> None:
        try:
            while True:
                session, msg = await receiver.get()
                
                try:
                    if msg.command_type == AttpCommand.ERR:
                        await self.transmitter.handle_response(msg)
                        await self.eventbus.emit(cast(EnhancedFrameTransmitterMixin, session), msg)
                        
                    elif msg.command_type in (
                        AttpCommand.ACK,
                        AttpCommand.DEFER,
                        AttpCommand.STREAMBOS,
                        AttpCommand.CHUNK,
                        AttpCommand.STREAMEOS,
                    ):
                        # await self.router.handle_response(msg)
                        await self.transmitter.handle_response(msg)

                    else:
                        await self.eventbus.emit(cast(EnhancedFrameTransmitterMixin, session), msg)

                except Exception:
                    traceback.print_exc()

                    if (
                        msg.command_type == AttpCommand.CALL
                        and msg.correlation_id
                    ):
                        await cast(EnhancedFrameTransmitterMixin, session).send_error(
                            msg.route_id,
                            error_frame=IAttpErr(
                                code=500,
                                message="Dispatcher failed to process frame."
                            ),
                            correlation_id=msg.correlation_id,
                        )

                finally:
                    receiver.task_done()

        except asyncio.CancelledError:
            # Graceful shutdown
            pass
