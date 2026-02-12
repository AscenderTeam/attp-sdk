import asyncio
from logging import Logger
from typing import Annotated

from ascender.core import Inject
from attp.client.authenticator import ConnectionAuthenticator
from attp.client.configs import AttpClientConfigs, ServiceDiscoveryConfigs
from attp.client.session_driver import ClientSessionDriver
from attp.server.session_driver import ServerSessionDriver
from attp.shared.lifecycle_service import LifecycleService

from attp_core.rs_api import AttpClientSession, PyAttpMessage

from attp.shared.multireceiver import AttpMultiReceiver
from attp.shared.namespaces.dispatcher import NamespaceDispatcher
from attp.shared.objects.dispatcher import AttpFrameDispatcher
from attp.shared.sessions.driver import AttpSessionDriver


class ServiceDiscovery(LifecycleService):
    def __init__(
        self, 
        configs: ServiceDiscoveryConfigs, 
        namespaces: NamespaceDispatcher,
        dispatcher: AttpFrameDispatcher,
        logger: Annotated[Logger, Inject("ASC_LOGGER")]
    ) -> None:
        super().__init__()
        self.configs = configs
        
        self.multireceiver = AttpMultiReceiver[tuple[AttpSessionDriver, PyAttpMessage]](lambda d: d[0].namespace, fanout_global=True, auto_create=True)
        self.namespaces = namespaces
        self.dispatcher = dispatcher
        
        self.conlock = asyncio.Lock()
        
        self.logger = logger
        self.is_active = False
    
    def activate(self):
        if not self.is_active:
            self.logger.info("Activating service discovery...")
            self.is_active = True
    
    async def start_initial_connections(self):
        for peer in self.configs.peers:
            if isinstance(peer, str):
                peer = AttpClientConfigs(remote_uri=peer)

            authenticator = self.configs.authenticator
            if isinstance(authenticator, type) and issubclass(authenticator, ConnectionAuthenticator):
                authenticator = authenticator(peer.remote_uri, peer.namespace)
            elif callable(authenticator):
                authenticator = authenticator(peer)
            try:
                await self.initiate_connection(peer, conn_authenticator=authenticator)
            except Exception as exc:
                self.logger.error(
                    "[cyan]ATTP[/] ┆ Failed to connect to peer %s (%s)",
                    peer.remote_uri,
                    exc,
                )
    
    async def on_startup(self):
        asyncio.create_task(self.start_initial_connections())
    
    async def on_shutdown(self):
        self.dispatcher.stop_all()
    
    async def on_session_termination(self, session_driver: ClientSessionDriver):
        try:
            self.namespaces.remove_session(session_driver.namespace, session_driver)
            self.logger.info("[cyan]ATTP[/] ┆ Session (%s) disconnected.", session_driver.session_id or "unknown")

        except ValueError:
            self.logger.info("[cyan]ATTP[/] ┆ Session (%s) disconnected before being registered", session_driver._session or "unknown")

    
    async def initiate_connection(self, config: AttpClientConfigs, conn_authenticator: ConnectionAuthenticator | None = None):
        client = AttpClientSession(config.remote_uri, limits=self.configs.limits.to_model())

        client = await client.connect(max_retries=self.configs.max_retries)

        if not client.session:
            raise ConnectionError("Failed to connect to the server.")
        
        driver = ClientSessionDriver(client.session, on_termination=self.on_session_termination)
        
        if not conn_authenticator:
            authenticator = ConnectionAuthenticator(config.remote_uri, config.namespace, config.authorization, config.data)
        else:
            authenticator = conn_authenticator
        
        try:
            namespace, _ = await driver.start(config.capabilities, authenticator)
        except TimeoutError:
            self.logger.error("[cyan]ATTP[/] ┆ Session (%s) %s failed to authenticate, flushing the connection!", client.session.peername, client.session.session_id)
            await driver.close()
            del driver
            return
        
        async with self.conlock:
            self.namespaces.add_session(namespace, driver)
            receiver = self.multireceiver.receiver(namespace)
            self.dispatcher.start(receiver)
        
        await driver.listen(receiver)
