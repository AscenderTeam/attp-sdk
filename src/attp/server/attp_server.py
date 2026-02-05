import asyncio
from ascender.core import Application

from attp.server.configs import AttpServerConfigs
from attp.shared.lifecycle_service import LifecycleService

from attp_core.rs_api import AttpTransport, AttpCommand, Session, Limits


class AttpServer(LifecycleService):
    def __init__(self, configs: AttpServerConfigs) -> None:
        super().__init__()
        self.transport = AttpTransport(
            host=configs.host, 
            port=configs.port,
            on_connection=lambda s: None, 
            limits=configs.limits.to_model()
        )
    
    async def on_startup(self):
        asyncio.create_task(self.transport.start_server())
    
    async def on_shutdown(self):
        await self.transport.stop_server()