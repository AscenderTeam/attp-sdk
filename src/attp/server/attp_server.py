import asyncio
import inspect
from logging import Logger
from typing import Annotated

from ascender.core import Inject

from attp.server.configs import AttpServerConfigs
from attp.server.session_driver import ServerSessionDriver
from attp.shared.lifecycle_service import LifecycleService

from attp_core.rs_api import AttpTransport, PyAttpMessage, Session, init_logging

from attp.shared.multireceiver import AttpMultiReceiver
from attp.shared.namespaces.dispatcher import NamespaceDispatcher
from attp.shared.objects.dispatcher import AttpFrameDispatcher
from attp.shared.sessions.driver import AttpSessionDriver


class AttpServer(LifecycleService):
    def __init__(
        self, 
        configs: AttpServerConfigs,
        namespaces: NamespaceDispatcher, 
        dispatcher: AttpFrameDispatcher,
        logger: Annotated[Logger, Inject("ASC_LOGGER")]
    ) -> None:
        super().__init__()
        self._startup_task: asyncio.Task | None = None
        if configs.verbose:
            init_logging(filter=configs.verbosity_level)
        
        self.transport = AttpTransport(
            host=configs.host, 
            port=configs.port,
            on_connection=self.on_connection, 
            limits=configs.limits.to_model()
        )
        self.namespaces = namespaces
        self.conlock = asyncio.Lock()
        
        self.logger = logger
        self.multireceiver = AttpMultiReceiver[tuple[AttpSessionDriver, PyAttpMessage]](lambda d: d[0].namespace, fanout_global=True, auto_create=True)
        
        self.dispatcher = dispatcher
        
        self.is_active = False
    
    def activate(self):
        if not self.is_active:
            self.logger.info("Activating ATTP Server...")
            self.is_active = True

    async def on_startup(self):
        self._startup_task = asyncio.create_task(self._start_server())
        self._startup_task.add_done_callback(self._log_startup_error)

    async def _start_server(self):
        await self.transport.start_server()

    def _log_startup_error(self, task: asyncio.Task):
        try:
            task.result()
        except Exception:
            self.logger.exception(
                "[cyan]ATTP[/] ┆ Failed to start server on %s:%s",
                self.transport.host,
                self.transport.port,
            )
    
    async def on_shutdown(self):
        await self.namespaces.terminate_all()
        if self.transport:
            await self.transport.stop_server()
    
    async def on_session_termination(self, session_driver: ServerSessionDriver):
        try:
            self.namespaces.remove_session(session_driver.namespace, session_driver)
            self.logger.info("[cyan]ATTP[/] ┆ Session (%s) disconnected.", session_driver.session_id or "unknown")

        except ValueError:
            self.logger.info("[cyan]ATTP[/] ┆ Session (%s) disconnected before being registered", session_driver._session or "unknown")
    
    async def on_connection(self, session: Session):
        self.logger.info("[cyan]ATTP[/] ┆ New connection from peer %s", session.peername)
        
        driver = ServerSessionDriver(session, self.on_session_termination)
        try:
            await driver.start()
        except TimeoutError:
            self.logger.error("[cyan]ATTP[/] ┆ Session (%s) %s failed to authenticate, flushing the connection!", session.peername, session.session_id)
            await driver.close()
            del driver
            return
        
        namespace = driver.namespace
        
        async with self.conlock:
            self.namespaces.add_session(namespace, driver)
            receiver = self.multireceiver.receiver(namespace)
            self.dispatcher.start(receiver)
            
        await driver.listen(receiver)
