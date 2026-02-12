from typing import TypeAlias

from attp.server.session_driver import ServerSessionDriver
from attp.shared.sessions.driver import AttpSessionDriver


Candidate: TypeAlias = AttpSessionDriver | ServerSessionDriver