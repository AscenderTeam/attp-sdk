from collections import defaultdict
from typing import MutableMapping, MutableSequence

from attp.server.session_driver import ServerSessionDriver
from attp.shared.utils.qsequence import QSequence


class NamespaceDispatcher:
    namespaces: MutableMapping[str, QSequence[ServerSessionDriver]]
    
    def __init__(self) -> None:
        self.namespaces = defaultdict(QSequence)
    
    def add_session(self, namespace: str, session: ServerSessionDriver):
        self.namespaces[namespace].append(session)
    
    def dispatch(self, namespace: str, sid: str | None = None):
        if sid:
            sessions = self.namespaces[namespace]
            session = next((s for s in sessions if s == sid), None)
    
            return session
        
        return self.namespaces[namespace]
    
    
