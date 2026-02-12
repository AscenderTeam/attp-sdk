import asyncio
from collections import defaultdict
from typing import Literal, MutableMapping, cast

from attp.shared.sessions.driver import AttpSessionDriver, SessionTerminatorMixin
from attp.shared.utils.qsequence import QSequence


class NamespaceDispatcher:
    namespaces: MutableMapping[str, QSequence[AttpSessionDriver]]
    
    def __init__(self) -> None:
        self.namespaces = defaultdict(QSequence[AttpSessionDriver])
    
    def add_session(self, namespace: str, session: AttpSessionDriver):
        self.namespaces[namespace].append(session)

    def remove_session(self, namespace: str, session: AttpSessionDriver):
        self.namespaces[namespace].remove(session)
    
    def dispatch(
        self,
        namespace: str,
        sid: str | None = None,
        role: Literal["client", "server"] | None = None
    ):
        print(self.namespaces)
        sessions = self.namespaces[namespace]
        if role:
            sessions = sessions.where(lambda s: s.role == role)

        if sid:
            session = sessions.find_or_none(lambda s: s.session_id == sid)
    
            return session
        
        return sessions
    
    async def terminate_all(self):
        _tasks = []
        
        for _, sessions in self.namespaces.items():
            for session in sessions:
                _tasks.append(cast(SessionTerminatorMixin, session).close())
            
        await asyncio.gather(*_tasks)
