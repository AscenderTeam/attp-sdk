from ascender.contrib import Service
from ascender.core import Application, inject


class LifecycleService(Service):
    _application: Application = inject(Application)
    
    def __init__(self) -> None:
        self._application.app.add_event_handler("startup", self.on_startup)
        self._application.app.add_event_handler("shutdown", self.on_shutdown)
    
    async def on_startup(self):
        ...
    
    async def on_shutdown(self):
        ...